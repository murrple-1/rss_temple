import logging
import uuid
from typing import Any, Collection, NamedTuple, cast

import dramatiq
from django.conf import settings
from django.core.cache import BaseCache, caches
from django.core.signals import setting_changed
from django.db import transaction
from django.db.models import OrderBy, Q
from django.dispatch import receiver
from django.utils import timezone
from dramatiq import Message, group
from dramatiq.errors import DramatiqError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from requests.exceptions import RequestException
from rest_framework.exceptions import APIException, NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from url_normalize import url_normalize

from api import content_type_util, feed_handler, grace_period_util, rss_requests
from api.cache_utils.archived_counts_lookup import (
    get_archived_counts_lookup_from_cache,
    get_archived_counts_lookup_task,
    save_archived_counts_lookup_to_cache,
)
from api.cache_utils.counts_lookup import (
    get_counts_lookup_from_cache,
    get_counts_lookup_task,
    save_counts_lookup_to_cache,
)
from api.cache_utils.subscription_datas import (
    delete_subscription_data_cache,
    get_subscription_datas_from_cache,
)
from api.exceptions import Conflict, InsufficientStorage
from api.exposed_feed_extractor import ExposedFeed, extract_exposed_feeds
from api.feed_handler import FeedHandlerError
from api.models import (
    AlternateFeedURL,
    Feed,
    FeedEntry,
    ReadFeedEntryUserMapping,
    RemovedFeed,
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
    QuerySerializer,
    TSConfigSerializer,
)
from api.text_classifier.lang_detector import detect_iso639_3
from api.text_classifier.prep_content import prep_for_lang_detection
from query_utils import fields as fieldutils

_logger = logging.getLogger("rss_temple.views.feed")

_EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS: float | None
_DOWNLOAD_MAX_BYTE_COUNT: int
_FEED_GET_REQUESTS_DRAMATIQ: bool
_FEED_GET_REQUESTS_DRAMATIQ_COUNTS_LOOKUP_TIMEOUT_SECONDS: float
_FEED_GET_REQUESTS_DRAMATIQ_ARCHIVED_COUNTS_LOOKUP_TIMEOUT_SECONDS: float


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS
    global _DOWNLOAD_MAX_BYTE_COUNT
    global _FEED_GET_REQUESTS_DRAMATIQ
    global _FEED_GET_REQUESTS_DRAMATIQ_COUNTS_LOOKUP_TIMEOUT_SECONDS
    global _FEED_GET_REQUESTS_DRAMATIQ_ARCHIVED_COUNTS_LOOKUP_TIMEOUT_SECONDS

    _EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS = settings.EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS
    _DOWNLOAD_MAX_BYTE_COUNT = settings.DOWNLOAD_MAX_BYTE_COUNT
    _FEED_GET_REQUESTS_DRAMATIQ = getattr(settings, "FEED_GET_REQUESTS_DRAMATIQ", True)
    _FEED_GET_REQUESTS_DRAMATIQ_COUNTS_LOOKUP_TIMEOUT_SECONDS = getattr(
        settings,
        "FEED_GET_REQUESTS_DRAMATIQ_COUNTS_LOOKUP_TIMEOUT_SECONDS",
        1000.0 * 10.0,
    )
    _FEED_GET_REQUESTS_DRAMATIQ_ARCHIVED_COUNTS_LOOKUP_TIMEOUT_SECONDS = getattr(
        settings,
        "FEED_GET_REQUESTS_DRAMATIQ_ARCHIVED_COUNTS_LOOKUP_TIMEOUT_SECONDS",
        1000 * 10.0,
    )


_load_global_settings()

_OBJECT_NAME = "feed"


class _PreprocessGetRequestFromCacheResults(NamedTuple):
    counts_lookup_cache_hit: bool | None
    archived_counts_lookup_cache_hit: bool | None


def _preprocess_get_request_from_cache(
    request: Request,
    cache: BaseCache,
    field_names: frozenset[str],
    user: User,
    feed_uuids: Collection[uuid.UUID],
) -> _PreprocessGetRequestFromCacheResults:
    if _FEED_GET_REQUESTS_DRAMATIQ:
        return _preprocess_get_request_from_cache__dramatiq(
            request, cache, field_names, user, feed_uuids
        )  # pragma: no cover
    else:
        return _preprocess_get_request_from_cache__sync(
            request, cache, field_names, user, feed_uuids
        )


def _preprocess_get_request_from_cache__dramatiq(
    request: Request,
    cache: BaseCache,
    field_names: frozenset[str],
    user: User,
    feed_uuids: Collection[uuid.UUID],
) -> _PreprocessGetRequestFromCacheResults:  # pragma: no cover
    broker = dramatiq.get_broker()

    messages: dict[str, Message | group] = {}

    counts_lookup: dict[uuid.UUID, Feed._CountsDescriptor] | None = None
    counts_lookup_cache_hit: bool | None = None
    if field_names.intersection(("readCount", "unreadCount")):
        counts_lookup, missing_counts_lookup_feed_uuids = get_counts_lookup_from_cache(
            user, feed_uuids, cache
        )

        if missing_counts_lookup_feed_uuids:
            g = group(
                [
                    Message(
                        queue_name="rss_temple",
                        actor_name="get_counts_lookup",
                        args=(
                            str(user.uuid),
                            str(uuid_),
                        ),
                        kwargs={},
                        options={
                            "max_age": (
                                _FEED_GET_REQUESTS_DRAMATIQ_COUNTS_LOOKUP_TIMEOUT_SECONDS
                                * 1000.0
                            ),
                        },
                    )
                    for uuid_ in missing_counts_lookup_feed_uuids
                ],
                broker=broker,
            )
            messages["counts"] = g.run()
            counts_lookup_cache_hit = False
        else:
            counts_lookup_cache_hit = True

    archived_counts_lookup: dict[uuid.UUID, int] | None = None
    archived_counts_lookup_cache_hit: bool | None = None
    if field_names.intersection(("archivedCount",)):
        (
            archived_counts_lookup,
            missing_archived_counts_lookup_feed_uuids,
        ) = get_archived_counts_lookup_from_cache(feed_uuids, cache)

        if missing_archived_counts_lookup_feed_uuids:
            g = group(
                [
                    Message(
                        queue_name="rss_temple",
                        actor_name="get_archived_counts_lookup",
                        args=(str(uuid_),),
                        kwargs={},
                        options={
                            "max_age": (
                                _FEED_GET_REQUESTS_DRAMATIQ_ARCHIVED_COUNTS_LOOKUP_TIMEOUT_SECONDS
                                * 1000.0
                            ),
                        },
                    )
                    for uuid_ in missing_archived_counts_lookup_feed_uuids
                ],
                broker=broker,
            )
            messages["archived_counts"] = g.run()
            archived_counts_lookup_cache_hit = False
        else:
            archived_counts_lookup_cache_hit = True

    for k, message in messages.items():
        if k == "counts":
            assert isinstance(message, group)

            missing_counts_lookup: dict[uuid.UUID, Feed._CountsDescriptor] = {}
            for counts_results in message.get_results(
                block=True,
                timeout=int(
                    _FEED_GET_REQUESTS_DRAMATIQ_COUNTS_LOOKUP_TIMEOUT_SECONDS * 1000.0
                ),
            ):
                counts_results = cast(dict[str, dict[str, Any]], counts_results)

                missing_counts_lookup.update(
                    {
                        uuid.UUID(fus): Feed._CountsDescriptor(
                            count_dict["unread_count"], count_dict["read_count"]
                        )
                        for fus, count_dict in counts_results.items()
                    }
                )

            save_counts_lookup_to_cache(user, missing_counts_lookup, cache)

            assert counts_lookup is not None
            counts_lookup.update(missing_counts_lookup)
        elif k == "archived_counts":
            assert isinstance(message, group)

            missing_archived_counts_lookup: dict[uuid.UUID, int] = {}
            for archived_counts_results in message.get_results(
                block=True,
                timeout=int(
                    _FEED_GET_REQUESTS_DRAMATIQ_ARCHIVED_COUNTS_LOOKUP_TIMEOUT_SECONDS
                    * 1000.0
                ),
            ):
                archived_counts_results = cast(dict[str, int], archived_counts_results)

                missing_archived_counts_lookup.update(
                    {
                        uuid.UUID(fus): count
                        for fus, count in archived_counts_results.items()
                    }
                )

            save_archived_counts_lookup_to_cache(missing_archived_counts_lookup, cache)

            assert archived_counts_lookup is not None
            archived_counts_lookup.update(missing_archived_counts_lookup)

    if counts_lookup is not None:
        setattr(
            request,
            "_counts_lookup",
            counts_lookup,
        )

    if archived_counts_lookup is not None:
        setattr(
            request,
            "_archived_counts_lookup",
            archived_counts_lookup,
        )

    return _PreprocessGetRequestFromCacheResults(
        counts_lookup_cache_hit, archived_counts_lookup_cache_hit
    )


def _preprocess_get_request_from_cache__sync(
    request: Request,
    cache: BaseCache,
    field_names: frozenset[str],
    user: User,
    feed_uuids: Collection[uuid.UUID],
) -> _PreprocessGetRequestFromCacheResults:
    counts_lookup_cache_hit: bool | None = None
    if field_names.intersection(("readCount", "unreadCount")):
        counts_lookup, missing_counts_lookup_feed_uuids = get_counts_lookup_from_cache(
            user, feed_uuids, cache
        )

        if missing_counts_lookup_feed_uuids:
            missing_counts_lookup: dict[uuid.UUID, Feed._CountsDescriptor] = {}

            for feed_uuid in feed_uuids:
                missing_counts_lookup_results = get_counts_lookup_task(
                    str(user.uuid), str(feed_uuid)
                )
                missing_counts_lookup.update(
                    {
                        uuid.UUID(fus): Feed._CountsDescriptor(
                            count_dict["unread_count"], count_dict["read_count"]
                        )
                        for fus, count_dict in missing_counts_lookup_results.items()
                    }
                )

            save_counts_lookup_to_cache(user, missing_counts_lookup, cache)

            counts_lookup.update(missing_counts_lookup)
            counts_lookup_cache_hit = False
        else:
            counts_lookup_cache_hit = True

        setattr(
            request,
            "_counts_lookup",
            counts_lookup,
        )

    archived_counts_lookup_cache_hit: bool | None = None
    if field_names.intersection(("archivedCount",)):
        (
            archived_counts_lookup,
            missing_archived_counts_lookup_feed_uuids,
        ) = get_archived_counts_lookup_from_cache(feed_uuids, cache)

        if missing_archived_counts_lookup_feed_uuids:
            missing_archived_counts_lookup: dict[uuid.UUID, int] = {}

            for feed_uuid in feed_uuids:
                missing_archived_counts_lookup_results = (
                    get_archived_counts_lookup_task(str(feed_uuid))
                )
                missing_archived_counts_lookup.update(
                    {
                        uuid.UUID(fus): count
                        for fus, count in missing_archived_counts_lookup_results.items()
                    }
                )

            save_archived_counts_lookup_to_cache(missing_archived_counts_lookup, cache)

            archived_counts_lookup.update(missing_archived_counts_lookup)
            archived_counts_lookup_cache_hit = False
        else:
            archived_counts_lookup_cache_hit = True

        setattr(
            request,
            "_archived_counts_lookup",
            archived_counts_lookup,
        )

    return _PreprocessGetRequestFromCacheResults(
        counts_lookup_cache_hit, archived_counts_lookup_cache_hit
    )


class FeedView(APIView):
    @extend_schema(
        summary="Get Single Feed",
        description="Get Single Feed",
        parameters=[FeedGetSerializer],
        request=None,
        responses=OpenApiTypes.OBJECT,
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

        field_maps: list[fieldutils.FieldMap] = serializer.validated_data["fields"]

        (
            subscription_datas,
            subscription_datas_cache_hit,
        ) = get_subscription_datas_from_cache(user, cache)

        feed: Feed
        try:
            feed = (
                Feed.annotate_subscription_data(
                    Feed.objects.all(),
                    user,
                    subscription_datas=subscription_datas,
                )
                .only(*fieldutils.generate_only_fields(field_maps))
                .get(
                    Q(feed_url=url)
                    | Q(
                        uuid__in=AlternateFeedURL.objects.filter(feed_url=url).values(
                            "feed_id"
                        )[:1]
                    )
                )
            )
        except Feed.DoesNotExist:
            feed = _save_feed(url)

        field_names = fieldutils.generate_field_names(field_maps)

        counts_lookup_cache_hit: bool | None
        archived_counts_lookup_cache_hit: bool | None
        try:
            (
                counts_lookup_cache_hit,
                archived_counts_lookup_cache_hit,
            ) = _preprocess_get_request_from_cache(
                request, cache, field_names, user, (feed.uuid,)
            )
        except DramatiqError as e:  # pragma: no cover
            _logger.exception("failed to get values from cache")
            raise APIException("failed to load data") from e

        ret_obj = fieldutils.generate_return_object(field_maps, feed, request, None)

        response = Response(ret_obj)
        response["X-Cache-Hit"] = ",".join(
            (
                "YES" if subscription_datas_cache_hit else "NO",
                (
                    ("YES" if counts_lookup_cache_hit else "NO")
                    if counts_lookup_cache_hit is not None
                    else "SKIP"
                ),
                (
                    ("YES" if archived_counts_lookup_cache_hit else "NO")
                    if archived_counts_lookup_cache_hit is not None
                    else "SKIP"
                ),
            ),
        )
        return response


class FeedsQueryView(APIView):
    @extend_schema(
        summary="Query for Feeds",
        description="Query for Feeds",
        request=GetManySerializer,
        responses=QuerySerializer,
    )
    def post(self, request: Request):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        ts_config_serializer = TSConfigSerializer(data=request.data)
        ts_config_serializer.is_valid(raise_exception=True)

        setattr(request, "_ts_config", ts_config_serializer.validated_data["ts_config"])

        serializer = GetManySerializer(
            data=request.data,
            context={"object_name": _OBJECT_NAME, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        count: int = serializer.validated_data["count"]
        skip: int = serializer.validated_data["skip"]
        sort: list[OrderBy] = serializer.validated_data["sort"]
        search: list[Q] = serializer.validated_data["search"]
        field_maps: list[fieldutils.FieldMap] = serializer.validated_data["fields"]
        return_objects: bool = serializer.validated_data["return_objects"]
        return_total_count: bool = serializer.validated_data["return_total_count"]

        (
            subscription_datas,
            subscription_datas_cache_hit,
        ) = get_subscription_datas_from_cache(user, cache)

        feeds = (
            Feed.annotate_search_vectors(
                Feed.annotate_subscription_data(
                    Feed.objects.all(),
                    user,
                    subscription_datas=subscription_datas,
                ),
                ts_config_serializer.validated_data["ts_config"],
            )
            .filter(*search)
            .only(*fieldutils.generate_only_fields(field_maps))
        )

        # TODO maybe improve performance https://archive.li/rxzuU ?
        feeds_qs = feeds.order_by(*sort)[skip : skip + count]

        feed_uuids = frozenset(f.uuid for f in feeds_qs)

        field_names = fieldutils.generate_field_names(field_maps)

        counts_lookup_cache_hit: bool | None
        archived_counts_lookup_cache_hit: bool | None
        try:
            (
                counts_lookup_cache_hit,
                archived_counts_lookup_cache_hit,
            ) = _preprocess_get_request_from_cache(
                request, cache, field_names, user, feed_uuids
            )
        except DramatiqError as e:  # pragma: no cover
            _logger.exception("failed to get values from cache")
            raise APIException("failed to load data") from e

        ret_obj: dict[str, Any] = {}

        if return_objects:
            objs: list[dict[str, Any]] = []
            for feed in feeds_qs:
                obj = fieldutils.generate_return_object(
                    field_maps, feed, request, feeds
                )
                objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = feeds.count()

        response = Response(ret_obj)
        response["X-Cache-Hit"] = ",".join(
            (
                "YES" if subscription_datas_cache_hit else "NO",
                (
                    ("YES" if counts_lookup_cache_hit else "NO")
                    if counts_lookup_cache_hit is not None
                    else "SKIP"
                ),
                (
                    ("YES" if archived_counts_lookup_cache_hit else "NO")
                    if archived_counts_lookup_cache_hit is not None
                    else "SKIP"
                ),
            )
        )
        return response


class FeedLookupView(APIView):
    @extend_schema(
        summary="Given a URL, return a list of the exposed RSS feeds",
        description="Given a URL, return a list of the exposed RSS feeds",
        parameters=[FeedFindQuerySerializer],
        responses=FeedFindSerializer(many=True),
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
    @extend_schema(
        summary="Subscribe to feed",
        description="Subscribe to feed",
        request=FeedSubscribeSerializer,
        responses={204: OpenApiResponse(description="No response body")},
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

        delete_subscription_data_cache(user, cache)

        return Response(status=204)

    @extend_schema(
        summary="Update subscription metadata",
        description="Update subscription metadata",
        request=FeedSubscribeSerializer,
        responses={204: OpenApiResponse(description="No response body")},
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

        delete_subscription_data_cache(user, cache)

        return Response(status=204)

    @extend_schema(
        summary="Unsubscribe from feed",
        description="Unsubscribe from feed",
        request=FeedGetSerializer,
        responses={204: OpenApiResponse(description="No response body")},
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

        delete_subscription_data_cache(user, cache)

        return Response(status=204)


def _save_feed(url: str):
    if RemovedFeed.objects.filter(feed_url=url).exists():
        raise NotFound("feed not found")

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
