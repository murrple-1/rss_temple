from typing import Any, cast

import requests
from django.db import transaction
from django.db.models import OrderBy, Q
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from url_normalize import url_normalize

from api import archived_feed_entry_util, feed_handler, query_utils, rss_requests
from api.exceptions import QueryException
from api.fields import FieldMap
from api.models import Feed, FeedEntry, SubscribedFeedUserMapping, User

_OBJECT_NAME = "feed"


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def feed(request: Request) -> Response:
    if request.method == "GET":
        return _feed_get(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def feeds_query(request: Request) -> Response:
    if request.method == "POST":
        return _feeds_query_post(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST", "PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def feed_subscribe(request: Request) -> Response:
    if request.method == "POST":
        return _feed_subscribe_post(request)
    elif request.method == "PUT":
        return _feed_subscribe_put(request)
    elif request.method == "DELETE":
        return _feed_subscribe_delete(request)
    else:  # pragma: no cover
        raise ValueError


def _save_feed(url: str):
    response: requests.Response
    try:
        response = rss_requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        raise QueryException("feed not found", 404)

    with transaction.atomic():
        d = feed_handler.text_2_d(response.text)
        feed = feed_handler.d_feed_2_feed(d.feed, url)
        feed.with_subscription_data()
        feed.save()

        feed_entries: list[FeedEntry] = []
        for d_entry in d.get("entries", []):
            feed_entry: FeedEntry
            try:
                feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
            except ValueError:  # pragma: no cover
                continue

            feed_entry.feed = feed
            feed_entries.append(feed_entry)

        FeedEntry.objects.bulk_create(feed_entries)

        return feed


def _feed_get(request: Request):
    url: str | None = request.GET.get("url")
    if not url:
        raise ValidationError({"url": "missing"})

    url = cast(str, url_normalize(url))

    field_maps: list[FieldMap]
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    feed: Feed
    try:
        feed = Feed.annotate_subscription_data(
            Feed.objects.all(), cast(User, request.user)
        ).get(feed_url=url)
    except Feed.DoesNotExist:
        try:
            feed = _save_feed(url)
        except QueryException as e:
            return Response(e.message, status=e.httpcode)

    ret_obj = query_utils.generate_return_object(field_maps, feed, request)

    return Response(ret_obj)


def _feeds_query_post(request: Request):
    if type(request.data) is not dict:
        raise ValidationError({".": "must be object"})  # pragma: no cover

    assert isinstance(request.data, dict)

    count: int
    try:
        count = query_utils.get_count(request.data)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    skip: int
    try:
        skip = query_utils.get_skip(request.data)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    sort: list[OrderBy]
    try:
        sort = query_utils.get_sort(request.data, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    search: list[Q]
    try:
        search = query_utils.get_search(request, request.data, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    field_maps: list[FieldMap]
    try:
        fields = query_utils.get_fields__json(request.data)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    return_objects: bool
    try:
        return_objects = query_utils.get_return_objects(request.data)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    return_total_count: bool
    try:
        return_total_count = query_utils.get_return_total_count(request.data)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    feeds = Feed.annotate_search_vectors(
        Feed.annotate_subscription_data(Feed.objects.all(), cast(User, request.user))
    ).filter(*search)

    ret_obj: dict[str, Any] = {}

    if return_objects:
        objs: list[dict[str, Any]] = []
        for feed in feeds.order_by(*sort)[skip : skip + count]:
            obj = query_utils.generate_return_object(field_maps, feed, request)
            objs.append(obj)

        ret_obj["objects"] = objs

    if return_total_count:
        ret_obj["totalCount"] = feeds.count()

    return Response(ret_obj)


def _feed_subscribe_post(request: Request):
    user = cast(User, request.user)

    url: str | None = request.GET.get("url")
    if not url:
        raise ValidationError({"url": "missing"})

    url = cast(str, url_normalize(url))

    feed: Feed
    try:
        feed = Feed.objects.get(feed_url=url)
    except Feed.DoesNotExist:
        try:
            feed = _save_feed(url)
        except QueryException as e:
            return Response(e.message, status=e.httpcode)

    custom_title = request.GET.get("customtitle")

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
        return Response("custom title already used", status=409)

    if feed.feed_url in existing_feed_urls:
        return Response("user already subscribed", status=409)

    read_mapping_generator = archived_feed_entry_util.read_mapping_generator_fn(
        feed, user
    )

    with transaction.atomic():
        SubscribedFeedUserMapping.objects.create(
            user=user, feed=feed, custom_feed_title=custom_title
        )

        archived_feed_entry_util.mark_archived_entries(read_mapping_generator)

    return Response(status=204)


def _feed_subscribe_put(request: Request):
    user = cast(User, request.user)

    url = request.GET.get("url")
    if not url:
        raise ValidationError({"url": "missing"})

    url = url_normalize(url)

    custom_title = request.GET.get("customtitle")

    subscribed_feed_mapping: SubscribedFeedUserMapping
    try:
        subscribed_feed_mapping = SubscribedFeedUserMapping.objects.get(
            user=user, feed__feed_url=url
        )
    except SubscribedFeedUserMapping.DoesNotExist:
        raise NotFound("not subscribed")

    if custom_title is not None:
        if (
            SubscribedFeedUserMapping.objects.exclude(uuid=subscribed_feed_mapping.uuid)
            .filter(user=user, custom_feed_title=custom_title)
            .exists()
        ):
            return Response("custom title already used", status=409)

    subscribed_feed_mapping.custom_feed_title = custom_title
    subscribed_feed_mapping.save(update_fields=["custom_feed_title"])

    return Response(status=204)


def _feed_subscribe_delete(request: Request):
    url = request.GET.get("url")
    if not url:
        raise ValidationError({"url": "missing"})

    url = url_normalize(url)

    count, _ = SubscribedFeedUserMapping.objects.filter(
        user=cast(User, request.user), feed__feed_url=url
    ).delete()

    if count < 1:
        raise NotFound("user not subscribed")

    return Response(status=204)
