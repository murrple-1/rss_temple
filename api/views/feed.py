from typing import Any, cast

import requests
import ujson
from django.db import transaction
from django.db.models import OrderBy, Q
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseBase,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)
from url_normalize import url_normalize

from api import archived_feed_entry_util, feed_handler, query_utils, rss_requests
from api.decorators import requires_authenticated_user
from api.exceptions import QueryException
from api.fields import FieldMap
from api.models import Feed, FeedEntry, SubscribedFeedUserMapping, User

_OBJECT_NAME = "feed"


@requires_authenticated_user()
def feed(request: HttpRequest) -> HttpResponseBase:
    permitted_methods = {"GET"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "GET":
        return _feed_get(request)
    else:  # pragma: no cover
        raise ValueError


@requires_authenticated_user()
def feeds_query(request: HttpRequest) -> HttpResponseBase:
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _feeds_query_post(request)
    else:  # pragma: no cover
        raise ValueError


@requires_authenticated_user()
def feed_subscribe(request: HttpRequest) -> HttpResponseBase:
    permitted_methods = {"POST", "PUT", "DELETE"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

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


def _feed_get(request: HttpRequest):
    url: str | None = request.GET.get("url")
    if not url:
        return HttpResponseBadRequest("'url' missing")

    url = cast(str, url_normalize(url))

    field_maps: list[FieldMap]
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    feed: Feed
    try:
        feed = Feed.annotate_subscription_data(
            Feed.objects.all(), cast(User, request.user)
        ).get(feed_url=url)
    except Feed.DoesNotExist:
        try:
            feed = _save_feed(url)
        except QueryException as e:
            return HttpResponse(e.message, status=e.httpcode)

    ret_obj = query_utils.generate_return_object(field_maps, feed, request)

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _feeds_query_post(request: HttpRequest):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_: Any
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    assert isinstance(json_, dict)

    count: int
    try:
        count = query_utils.get_count(json_)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    skip: int
    try:
        skip = query_utils.get_skip(json_)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    sort: list[OrderBy]
    try:
        sort = query_utils.get_sort(json_, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    search: list[Q]
    try:
        search = query_utils.get_search(request, json_, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    field_maps: list[FieldMap]
    try:
        fields = query_utils.get_fields__json(json_)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    return_objects: bool
    try:
        return_objects = query_utils.get_return_objects(json_)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    return_total_count: bool
    try:
        return_total_count = query_utils.get_return_total_count(json_)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

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

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _feed_subscribe_post(request: HttpRequest):
    user = cast(User, request.user)

    url: str | None = request.GET.get("url")
    if not url:
        return HttpResponseBadRequest("'url' missing")

    url = cast(str, url_normalize(url))

    feed: Feed
    try:
        feed = Feed.objects.get(feed_url=url)
    except Feed.DoesNotExist:
        try:
            feed = _save_feed(url)
        except QueryException as e:
            return HttpResponse(e.message, status=e.httpcode)

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
        return HttpResponse("custom title already used", status=409)

    if feed.feed_url in existing_feed_urls:
        return HttpResponse("user already subscribed", status=409)

    read_mapping_generator = archived_feed_entry_util.read_mapping_generator_fn(
        feed, user
    )

    with transaction.atomic():
        SubscribedFeedUserMapping.objects.create(
            user=user, feed=feed, custom_feed_title=custom_title
        )

        archived_feed_entry_util.mark_archived_entries(read_mapping_generator)

    return HttpResponse(status=204)


def _feed_subscribe_put(request: HttpRequest):
    user = cast(User, request.user)

    url = request.GET.get("url")
    if not url:
        return HttpResponseBadRequest("'url' missing")

    url = url_normalize(url)

    custom_title = request.GET.get("customtitle")

    subscribed_feed_mapping: SubscribedFeedUserMapping
    try:
        subscribed_feed_mapping = SubscribedFeedUserMapping.objects.get(
            user=user, feed__feed_url=url
        )
    except SubscribedFeedUserMapping.DoesNotExist:
        return HttpResponseNotFound("not subscribed")

    if custom_title is not None:
        if (
            SubscribedFeedUserMapping.objects.exclude(uuid=subscribed_feed_mapping.uuid)
            .filter(user=user, custom_feed_title=custom_title)
            .exists()
        ):
            return HttpResponse("custom title already used", status=409)

    subscribed_feed_mapping.custom_feed_title = custom_title
    subscribed_feed_mapping.save(update_fields=["custom_feed_title"])

    return HttpResponse(status=204)


def _feed_subscribe_delete(request: HttpRequest):
    url = request.GET.get("url")
    if not url:
        return HttpResponseBadRequest("'url' missing")

    url = url_normalize(url)

    count, _ = SubscribedFeedUserMapping.objects.filter(
        user=cast(User, request.user), feed__feed_url=url
    ).delete()

    if count < 1:
        return HttpResponseNotFound("user not subscribed")

    return HttpResponse(status=204)
