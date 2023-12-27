from typing import Any, cast

import requests
from django.conf import settings
from django.core.cache import BaseCache, caches
from django.core.signals import setting_changed
from django.db import transaction
from django.db.models import OrderBy, Q
from django.dispatch import receiver
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from url_normalize import url_normalize

from api import feed_handler
from api import fields as fieldutils
from api import grace_period_util, rss_requests
from api.exceptions import Conflict
from api.exposed_feed_extractor import ExposedFeed, extract_exposed_feeds
from api.fields import FieldMap
from api.models import (
    Feed,
    FeedEntry,
    ReadFeedEntryUserMapping,
    SubscribedFeedUserMapping,
    User,
)
from api.serializers import (
    FeedFindQuerySerializer,
    FeedFindSerializer,
    FeedGetSerializer,
    FeedSubscribeSerializer,
    GetManySerializer,
)
from api.text_classifier.lang_detector import detect_iso639_3
from api.text_classifier.prep_content import prep_for_lang_detection

_EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS: float | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS

    _EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS = settings.EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS


_load_global_settings()

_OBJECT_NAME = "feed"


class FeedView(APIView):
    @swagger_auto_schema(
        operation_summary="Get Single Feed",
        operation_description="Get Single Feed",
        query_serializer=FeedGetSerializer,
    )
    def get(self, request: Request):
        serializer = FeedGetSerializer(
            data=request.query_params,
            context={"object_name": _OBJECT_NAME, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        url = cast(str, url_normalize(serializer.validated_data["url"]))

        field_maps: list[FieldMap] = serializer.validated_data["fields"]

        feed: Feed
        try:
            feed = Feed.annotate_subscription_data(
                Feed.objects.all(), cast(User, request.user)
            ).get(feed_url=url)
        except Feed.DoesNotExist:
            feed = _save_feed(url)

        ret_obj = fieldutils.generate_return_object(field_maps, feed, request, None)

        return Response(ret_obj)


class FeedsQueryView(APIView):
    @swagger_auto_schema(
        operation_summary="Query for Feeds",
        operation_description="Query for Feeds",
        request_body=GetManySerializer,
    )
    def post(self, request: Request):
        serializer = GetManySerializer(
            data=request.data,
            context={"object_name": _OBJECT_NAME, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        count: int = serializer.validated_data["count"]
        skip: int = serializer.validated_data["skip"]
        sort: list[OrderBy] = serializer.validated_data["sort"]
        search: list[Q] = serializer.validated_data["search"]
        field_maps: list[FieldMap] = serializer.validated_data["fields"]
        return_objects: bool = serializer.validated_data["return_objects"]
        return_total_count: bool = serializer.validated_data["return_total_count"]

        feeds = Feed.annotate_search_vectors(
            Feed.annotate_subscription_data(
                Feed.objects.all(), cast(User, request.user)
            )
        ).filter(*search)

        ret_obj: dict[str, Any] = {}

        if return_objects:
            objs: list[dict[str, Any]] = []
            for feed in feeds.order_by(*sort)[skip : skip + count]:
                obj = fieldutils.generate_return_object(
                    field_maps, feed, request, feeds
                )
                objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = feeds.count()

        return Response(ret_obj)


class FeedLookupView(APIView):
    @swagger_auto_schema(
        operation_summary="Given a URL, return a list of the exposed RSS feeds",
        operation_description="Given a URL, return a list of the exposed RSS feeds",
        query_serializer=FeedFindQuerySerializer,
        responses={200: FeedFindSerializer(many=True)},
    )
    def get(self, request: Request):
        cache: BaseCache = caches["default"]

        serializer = FeedFindQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        url = cast(str, url_normalize(serializer.validated_data["url"]))

        cache_key = f"exposed_feeds_{url}"
        exposed_feeds: list[ExposedFeed] | None = cache.get(cache_key)
        cache_hit = True
        if exposed_feeds is None:
            cache_hit = False
            exposed_feeds = extract_exposed_feeds(url)
            cache.set(cache_key, exposed_feeds, _EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS)

        response = Response(
            [
                {
                    "title": ef.title,
                    "href": ef.href,
                }
                for ef in exposed_feeds
            ]
        )
        response["X-Cache-Hit"] = "YES" if cache_hit else "NO"
        return response


class FeedSubscribeView(APIView):
    @swagger_auto_schema(
        operation_summary="Subscribe to feed",
        operation_description="Subscribe to feed",
        request_body=FeedSubscribeSerializer,
    )
    def post(self, request: Request):
        user = cast(User, request.user)

        serializer = FeedSubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        url = cast(str, url_normalize(serializer.validated_data["url"]))

        feed: Feed
        try:
            feed = Feed.objects.get(feed_url=url)
        except Feed.DoesNotExist:
            feed = _save_feed(url)

        custom_title: str | None = serializer.validated_data.get("custom_title")

        existing_subscription_list = list(
            SubscribedFeedUserMapping.objects.filter(user=user).values_list(
                "feed__feed_url", "custom_feed_title"
            )
        )

        existing_feed_urls = frozenset(t[0] for t in existing_subscription_list)
        existing_custom_titles = frozenset(
            t[1] for t in existing_subscription_list if t[1] is not None
        )

        if custom_title is not None and custom_title in existing_custom_titles:
            raise Conflict("custom title already used")

        if feed.feed_url in existing_feed_urls:
            raise Conflict("user already subscribed")

        read_mappings = grace_period_util.generate_grace_period_read_entries(feed, user)

        with transaction.atomic():
            SubscribedFeedUserMapping.objects.create(
                user=user, feed=feed, custom_feed_title=custom_title
            )

            ReadFeedEntryUserMapping.objects.bulk_create(read_mappings)

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Update subscription metadata",
        operation_description="Update subscription metadata",
        request_body=FeedSubscribeSerializer,
    )
    def put(self, request: Request):
        user = cast(User, request.user)

        serializer = FeedSubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = request.data.get("url")

        url = url_normalize(serializer.validated_data["url"])

        custom_title: str | None = serializer.validated_data.get("custom_title")

        subscribed_feed_mapping: SubscribedFeedUserMapping
        try:
            subscribed_feed_mapping = SubscribedFeedUserMapping.objects.get(
                user=user, feed__feed_url=url
            )
        except SubscribedFeedUserMapping.DoesNotExist:
            raise NotFound("not subscribed")

        if custom_title is not None:
            if (
                SubscribedFeedUserMapping.objects.exclude(
                    uuid=subscribed_feed_mapping.uuid
                )
                .filter(user=user, custom_feed_title=custom_title)
                .exists()
            ):
                raise Conflict("custom title already used")

        subscribed_feed_mapping.custom_feed_title = custom_title
        subscribed_feed_mapping.save(update_fields=["custom_feed_title"])

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Unsubscribe from feed",
        operation_description="Unsubscribe from feed",
        request_body=FeedGetSerializer,
    )
    def delete(self, request: Request):
        serializer = FeedGetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        url = url_normalize(serializer.validated_data["url"])

        count, _ = SubscribedFeedUserMapping.objects.filter(
            user=cast(User, request.user), feed__feed_url=url
        ).delete()

        if count < 1:
            raise NotFound("user not subscribed")

        return Response(status=204)


def _save_feed(url: str):
    response: requests.Response
    try:
        response = rss_requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        raise NotFound("feed not found")

    now = timezone.now()

    with transaction.atomic():
        d = feed_handler.text_2_d(response.text)
        feed = feed_handler.d_feed_2_feed(d.feed, url, now)
        feed.with_subscription_data()
        feed.save()

        feed_entries: list[FeedEntry] = []
        for d_entry in d.get("entries", []):
            feed_entry: FeedEntry
            try:
                feed_entry = feed_handler.d_entry_2_feed_entry(d_entry, now)
            except ValueError:  # pragma: no cover
                continue

            feed_entry.feed = feed

            feed_entry.language_id = detect_iso639_3(
                prep_for_lang_detection(feed_entry.title, feed_entry.content)
            )

            feed_entries.append(feed_entry)

        FeedEntry.objects.bulk_create(feed_entries, ignore_conflicts=True)

        return feed
