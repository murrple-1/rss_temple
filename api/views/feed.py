from typing import Any, cast

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.core.signals import setting_changed
from django.db import transaction
from django.db.models import OrderBy, Q
from django.dispatch import receiver
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from requests.exceptions import RequestException
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from url_normalize import url_normalize

from api import content_type_util, feed_handler
from api import fields as fieldutils
from api import grace_period_util, rss_requests
from api.exceptions import Conflict, InsufficientStorage
from api.exposed_feed_extractor import ExposedFeed, extract_exposed_feeds
from api.feed_handler import FeedHandlerError
from api.fields import FieldMap
from api.models import (
    AlternateFeedURL,
    Feed,
    FeedEntry,
    ReadFeedEntryUserMapping,
    SubscribedFeedUserMapping,
    User,
)
from api.requests_extensions import ResponseTooBig, safe_response_text
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
_DOWNLOAD_MAX_BYTE_COUNT: int


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS
    global _DOWNLOAD_MAX_BYTE_COUNT

    _EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS = settings.EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS
    _DOWNLOAD_MAX_BYTE_COUNT = settings.DOWNLOAD_MAX_BYTE_COUNT


_load_global_settings()

_OBJECT_NAME = "feed"


def _generate_subscription_datas(user: User) -> list[Feed._SubscriptionData]:
    return [
        {
            "uuid": sfum.feed_id,
            "custom_title": sfum.custom_feed_title,
        }
        for sfum in SubscribedFeedUserMapping.objects.filter(user=user).iterator()
    ]


class FeedView(APIView):
    @swagger_auto_schema(
        operation_summary="Get Single Feed",
        operation_description="Get Single Feed",
        query_serializer=FeedGetSerializer,
    )
    def get(self, request: Request):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        serializer = FeedGetSerializer(
            data=request.query_params,
            context={"object_name": _OBJECT_NAME, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        url = cast(str, url_normalize(serializer.validated_data["url"]))

        field_maps: list[FieldMap] = serializer.validated_data["fields"]

        cache_key = f"feed_subscription_datas__{user.uuid}"
        subscription_datas: list[Feed._SubscriptionData] | None = cache.get(cache_key)
        if subscription_datas is None:
            subscription_datas = _generate_subscription_datas(user)
            cache.set(
                cache_key,
                subscription_datas,
                60.0 * 5.0,  # TODO make setting
            )

        feed: Feed
        try:
            feed = Feed.annotate_subscription_data__case(
                Feed.objects.all(), subscription_datas
            ).get(
                Q(feed_url=url)
                | Q(
                    uuid__in=AlternateFeedURL.objects.filter(feed_url=url).values(
                        "feed_id"
                    )[:1]
                )
            )
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
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

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

        cache_key = f"feed_subscription_datas__{user.uuid}"
        subscription_datas: list[Feed._SubscriptionData] | None = cache.get(cache_key)
        if subscription_datas is None:
            subscription_datas = _generate_subscription_datas(user)
            cache.set(
                cache_key,
                subscription_datas,
                60.0 * 5.0,  # TODO make setting
            )

        feeds = Feed.annotate_search_vectors(
            Feed.annotate_subscription_data__case(
                Feed.objects.all(), subscription_datas
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
            try:
                exposed_feeds = extract_exposed_feeds(url, _DOWNLOAD_MAX_BYTE_COUNT)
            except ResponseTooBig:  # pragma: no cover
                raise InsufficientStorage
            cache_hit = False
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
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        serializer = FeedSubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        url = cast(str, url_normalize(serializer.validated_data["url"]))

        feed: Feed
        try:
            feed = Feed.objects.get(
                Q(feed_url=url)
                | Q(
                    uuid__in=AlternateFeedURL.objects.filter(feed_url=url).values(
                        "feed_id"
                    )[:1]
                )
            )
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

        cache.delete(f"feed_subscription_datas__{user.uuid}")

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Update subscription metadata",
        operation_description="Update subscription metadata",
        request_body=FeedSubscribeSerializer,
    )
    def put(self, request: Request):
        cache: BaseCache = caches["default"]

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

        cache.delete(f"feed_subscription_datas__{user.uuid}")

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Unsubscribe from feed",
        operation_description="Unsubscribe from feed",
        request_body=FeedGetSerializer,
    )
    def delete(self, request: Request):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        serializer = FeedGetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        url = cast(str, url_normalize(serializer.validated_data["url"]))

        count, _ = SubscribedFeedUserMapping.objects.filter(
            user=user, feed__feed_url=url
        ).delete()

        if count < 1:
            raise NotFound("user not subscribed")

        cache.delete(f"feed_subscription_datas__{user.uuid}")

        return Response(status=204)


def _save_feed(url: str):
    response_text: str
    try:
        with rss_requests.get(url, stream=True) as response:
            response.raise_for_status()

            content_type = response.headers.get("Content-Type")
            if content_type is not None and not content_type_util.is_feed(content_type):
                raise NotFound("feed not found")

            response_text = safe_response_text(response, _DOWNLOAD_MAX_BYTE_COUNT)
    except RequestException as e:
        raise NotFound("feed not found") from e
    except ResponseTooBig as e:  # pragma: no cover
        raise InsufficientStorage from e

    now = timezone.now()

    d: Any
    try:
        d = feed_handler.text_2_d(response_text)
    except FeedHandlerError:
        raise NotFound("feed not found")

    feed = feed_handler.d_feed_2_feed(d.feed, url, now)

    with transaction.atomic():
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
