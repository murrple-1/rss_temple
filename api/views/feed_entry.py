import uuid as uuid_
from collections import Counter
from typing import Any, Generator, cast

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.core.signals import setting_changed
from django.db import transaction
from django.db.models import F, OrderBy, Q
from django.dispatch import receiver
from django.http.response import HttpResponseBase
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.cache_utils.counts_lookup import increment_read_in_counts_lookup_cache
from api.cache_utils.favorite_feed_entry_uuids import (
    delete_favorite_feed_entry_uuids_cache,
    get_favorite_feed_entry_uuids_from_cache,
)
from api.cache_utils.read_feed_entry_uuids import (
    delete_read_feed_entry_uuids_cache,
    get_read_feed_entry_uuids_from_cache,
)
from api.cache_utils.subscription_datas import get_subscription_datas_from_cache
from api.django_extensions import bulk_create_iter
from api.models import FeedEntry, ReadFeedEntryUserMapping, User
from api.serializers import (
    FeedEntriesMarkReadSerializer,
    FeedEntriesMarkSerializer,
    FeedEntryLanguagesQuerySerializer,
    FeedEntryLanguagesSerializer,
    GetManySerializer,
    GetSingleSerializer,
    QuerySerializer,
    StableQueryCreateSerializer,
    StableQueryMultipleSerializer,
)
from query_utils import fields as fieldutils

_MAX_FEED_ENTRIES_STABLE_QUERY_COUNT: int
_FEED_ENTRY_LANGUAGES_CACHE_TIMEOUT_SECONDS: float


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _MAX_FEED_ENTRIES_STABLE_QUERY_COUNT
    global _FEED_ENTRY_LANGUAGES_CACHE_TIMEOUT_SECONDS

    _MAX_FEED_ENTRIES_STABLE_QUERY_COUNT = settings.MAX_FEED_ENTRIES_STABLE_QUERY_COUNT
    _FEED_ENTRY_LANGUAGES_CACHE_TIMEOUT_SECONDS = (
        settings.FEED_ENTRY_LANGUAGES_CACHE_TIMEOUT_SECONDS
    )


_load_global_settings()

_OBJECT_NAME = "feedentry"


class FeedEntryView(APIView):
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(*args, **kwargs)

    @extend_schema(
        summary="Get Single Feed Entry",
        description="Get Single Feed Entry",
        parameters=[GetSingleSerializer],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request, uuid: uuid_.UUID):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        serializer = GetSingleSerializer(
            data=request.query_params,
            context={"object_name": _OBJECT_NAME, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        field_maps: list[fieldutils.FieldMap] = serializer.validated_data["fields"]

        (
            subscription_datas,
            subscription_datas_cache_hit,
        ) = get_subscription_datas_from_cache(user, cache)
        (
            read_feed_entry_uuids,
            read_feed_entry_uuids_cache_hit,
        ) = get_read_feed_entry_uuids_from_cache(user, cache)
        (
            favorite_feed_entry_uuids,
            favorite_feed_entry_uuids_cache_hit,
        ) = get_favorite_feed_entry_uuids_from_cache(user, cache)

        feed_entry: FeedEntry
        try:
            feed_entry = (
                FeedEntry.annotate_search_vectors(
                    FeedEntry.annotate_user_data(
                        FeedEntry.objects.all(),
                        user,
                        subscription_datas=subscription_datas,
                        read_feed_entry_uuids=read_feed_entry_uuids,
                        favorite_feed_entry_uuids=favorite_feed_entry_uuids,
                    )
                )
                .only(*fieldutils.generate_only_fields(field_maps).union({"language"}))
                .select_related("language")
                .get(uuid=uuid)
            )
        except FeedEntry.DoesNotExist:
            raise NotFound("feed entry not found")

        ret_obj = fieldutils.generate_return_object(
            field_maps, feed_entry, request, None
        )

        response = Response(ret_obj)
        response["X-Cache-Hit"] = ",".join(
            (
                "YES" if subscription_datas_cache_hit else "NO",
                "YES" if read_feed_entry_uuids_cache_hit else "NO",
                "YES" if favorite_feed_entry_uuids_cache_hit else "NO",
            )
        )

        return response


class FeedEntriesQueryView(APIView):
    @extend_schema(
        summary="Query for Feed Entries",
        description="Query for Feed Entries",
        parameters=[GetManySerializer],
        request=None,
        responses=QuerySerializer,
    )
    def post(self, request: Request):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        serializer = GetManySerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
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
        (
            read_feed_entry_uuids,
            read_feed_entry_uuids_cache_hit,
        ) = get_read_feed_entry_uuids_from_cache(user, cache)
        (
            favorite_feed_entry_uuids,
            favorite_feed_entry_uuids_cache_hit,
        ) = get_favorite_feed_entry_uuids_from_cache(user, cache)

        feed_entries = (
            FeedEntry.annotate_search_vectors(
                FeedEntry.annotate_user_data(
                    FeedEntry.objects.all(),
                    user,
                    subscription_datas=subscription_datas,
                    read_feed_entry_uuids=read_feed_entry_uuids,
                    favorite_feed_entry_uuids=favorite_feed_entry_uuids,
                )
            )
            .filter(*search)
            .only(*fieldutils.generate_only_fields(field_maps).union({"language"}))
            .select_related("language")
        )

        ret_obj: dict[str, Any] = {}

        if return_objects:
            objs: list[dict[str, Any]] = []
            for feed_entry in feed_entries.order_by(*sort)[skip : skip + count]:
                obj = fieldutils.generate_return_object(
                    field_maps, feed_entry, request, feed_entries
                )
                objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = feed_entries.count()

        response = Response(ret_obj)
        response["X-Cache-Hit"] = ",".join(
            (
                "YES" if subscription_datas_cache_hit else "NO",
                "YES" if read_feed_entry_uuids_cache_hit else "NO",
                "YES" if favorite_feed_entry_uuids_cache_hit else "NO",
            )
        )
        return response


class FeedEntriesQueryStableCreateView(APIView):
    @extend_schema(
        summary="Stable Query Creation for Feed Entries",
        description="Returns a token to access to stable query",
        request=StableQueryCreateSerializer,
        responses=OpenApiTypes.STR,
    )
    def post(self, request: Request):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        stable_query_cache: BaseCache = caches["stable_query"]

        serializer = StableQueryCreateSerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        sort: list[OrderBy] = serializer.validated_data["sort"]
        search: list[Q] = serializer.validated_data["search"]

        token = f"feedentry-{uuid_.uuid4().int}"

        (
            subscription_datas,
            subscription_datas_cache_hit,
        ) = get_subscription_datas_from_cache(user, cache)
        (
            read_feed_entry_uuids,
            read_feed_entry_uuids_cache_hit,
        ) = get_read_feed_entry_uuids_from_cache(user, cache)
        (
            favorite_feed_entry_uuids,
            favorite_feed_entry_uuids_cache_hit,
        ) = get_favorite_feed_entry_uuids_from_cache(user, cache)

        stable_query_cache.set(
            token,
            list(
                FeedEntry.annotate_search_vectors(
                    FeedEntry.annotate_user_data(
                        FeedEntry.objects.all(),
                        user,
                        subscription_datas=subscription_datas,
                        read_feed_entry_uuids=read_feed_entry_uuids,
                        favorite_feed_entry_uuids=favorite_feed_entry_uuids,
                    )
                )
                .filter(*search)
                .order_by(*sort)
                .values_list("uuid", flat=True)[:_MAX_FEED_ENTRIES_STABLE_QUERY_COUNT]
            ),
        )

        response = Response(token)
        response["X-Cache-Hit"] = ",".join(
            (
                "YES" if subscription_datas_cache_hit else "NO",
                "YES" if read_feed_entry_uuids_cache_hit else "NO",
                "YES" if favorite_feed_entry_uuids_cache_hit else "NO",
            )
        )
        return response


class FeedEntriesQueryStableView(APIView):
    @extend_schema(
        summary="Stable Query for Feed Entries",
        description="Stable Query for Feed Entries",
        request=StableQueryMultipleSerializer,
        responses=QuerySerializer,
    )
    def post(self, request: Request):
        user = cast(User, request.user)

        cache: BaseCache = caches["default"]

        stable_query_cache: BaseCache = caches["stable_query"]

        serializer = StableQueryMultipleSerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        token: str = serializer.validated_data["token"]
        count: int = serializer.validated_data["count"]
        skip: int = serializer.validated_data["skip"]
        field_maps: list[fieldutils.FieldMap] = serializer.validated_data["fields"]
        return_objects: bool = serializer.validated_data["return_objects"]
        return_total_count: bool = serializer.validated_data["return_total_count"]

        stable_query_cache.touch(token)
        uuids = stable_query_cache.get(token, [])

        ret_obj: dict[str, Any] = {}

        subscription_datas_cache_hit: bool | None = None
        read_feed_entry_uuids_cache_hit: bool | None = None
        favorite_feed_entry_uuids_cache_hit: bool | None = None
        if return_objects:
            current_uuids = uuids[skip : skip + count]

            (
                subscription_datas,
                subscription_datas_cache_hit,
            ) = get_subscription_datas_from_cache(user, cache)
            (
                read_feed_entry_uuids,
                read_feed_entry_uuids_cache_hit,
            ) = get_read_feed_entry_uuids_from_cache(user, cache)
            (
                favorite_feed_entry_uuids,
                favorite_feed_entry_uuids_cache_hit,
            ) = get_favorite_feed_entry_uuids_from_cache(user, cache)

            feed_entries: dict[uuid_.UUID, FeedEntry] = {
                feed_entry.uuid: feed_entry
                for feed_entry in FeedEntry.annotate_user_data(
                    FeedEntry.objects.filter(uuid__in=current_uuids)
                    .only(
                        *fieldutils.generate_only_fields(field_maps).union(
                            {"uuid", "language"}
                        )
                    )
                    .select_related("language"),
                    user,
                    subscription_datas=subscription_datas,
                    read_feed_entry_uuids=read_feed_entry_uuids,
                    favorite_feed_entry_uuids=favorite_feed_entry_uuids,
                )
            }

            objs: list[dict[str, Any]] = []
            if len(current_uuids) == len(feed_entries):
                for uuid in current_uuids:
                    feed_entry = feed_entries[uuid]
                    obj = fieldutils.generate_return_object(
                        field_maps, feed_entry, request, feed_entries.values()
                    )
                    objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = len(uuids)

        response = Response(ret_obj)
        if (
            subscription_datas_cache_hit is not None
            and read_feed_entry_uuids_cache_hit is not None
            and favorite_feed_entry_uuids_cache_hit is not None
        ):
            response["X-Cache-Hit"] = ",".join(
                (
                    "YES" if subscription_datas_cache_hit else "NO",
                    "YES" if read_feed_entry_uuids_cache_hit else "NO",
                    "YES" if favorite_feed_entry_uuids_cache_hit else "NO",
                )
            )
        return response


class FeedEntryReadView(APIView):
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(*args, **kwargs)

    @extend_schema(
        summary="Mark a feed entry as 'read'",
        description="Mark a feed entry as 'read'",
        request=None,
        responses=OpenApiTypes.STR,
    )
    def post(self, request: Request, *, uuid: uuid_.UUID):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        read_feed_entry_user_mapping: ReadFeedEntryUserMapping
        with transaction.atomic():
            feed_entry: FeedEntry
            try:
                feed_entry = FeedEntry.objects.get(uuid=uuid)
            except FeedEntry.DoesNotExist:
                raise NotFound("feed entry not found")

            ret_obj: str
            if feed_entry.is_archived:
                ret_obj = ""
            else:
                created: bool
                with transaction.atomic():
                    (
                        read_feed_entry_user_mapping,
                        created,
                    ) = ReadFeedEntryUserMapping.objects.get_or_create(
                        feed_entry=feed_entry, user=user
                    )

                    if created:
                        User.objects.filter(uuid=user.uuid).update(
                            read_feed_entries_counter=F("read_feed_entries_counter") + 1
                        )

                    ret_obj = read_feed_entry_user_mapping.read_at.isoformat()

                if created:
                    increment_read_in_counts_lookup_cache(
                        user, {feed_entry.feed_id: 1}, cache
                    )
                    delete_read_feed_entry_uuids_cache(user, cache)

        return Response(ret_obj)

    @extend_schema(
        summary="Unmark a feed entry as 'read'",
        description="Unmark a feed entry as 'read'",
        request=None,
        responses={204: OpenApiResponse(description="No response body")},
    )
    def delete(self, request: Request, *, uuid: uuid_.UUID):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        deleted: bool
        with transaction.atomic():
            feed_entry: FeedEntry
            try:
                feed_entry = FeedEntry.objects.get(uuid=uuid)
            except FeedEntry.DoesNotExist:
                return Response(status=204)

            _, deletes = ReadFeedEntryUserMapping.objects.filter(
                user=user, feed_entry=feed_entry
            ).delete()
            deleted_count = deletes.get("api.ReadFeedEntryUserMapping", 0)
            deleted = deleted_count > 0
            if deleted:
                User.objects.filter(uuid=user.uuid).update(
                    read_feed_entries_counter=F("read_feed_entries_counter")
                    - deleted_count
                )

        if deleted:
            increment_read_in_counts_lookup_cache(user, {feed_entry.feed_id: -1}, cache)
            delete_read_feed_entry_uuids_cache(user, cache)

        return Response(status=204)


class FeedEntriesReadView(APIView):
    @extend_schema(
        summary="Mark multiple feed entries as 'read'",
        description="Mark multiple feed entries as 'read'",
        request=FeedEntriesMarkReadSerializer,
        responses={204: OpenApiResponse(description="No response body")},
    )
    def post(self, request: Request):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        serializer = FeedEntriesMarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        q: Q | None = None
        if feed_uuids := serializer.validated_data.get("feed_uuids"):
            if q is None:
                q = Q(feed__uuid__in=feed_uuids)
            else:
                q |= Q(feed__uuid__in=feed_uuids)  # pragma: no cover

        if feed_entry_uuids := serializer.validated_data.get("feed_entry_uuids"):
            if q is None:
                q = Q(uuid__in=feed_entry_uuids)
            else:
                q |= Q(uuid__in=feed_entry_uuids)

        if q is None:
            raise ValidationError("no entries to mark read")

        q = (
            Q(is_archived=False)
            & ~Q(uuid__in=user.read_feed_entries.values("uuid"))
            & q
        )

        increment_counter: Counter[uuid_.UUID] = Counter()

        def generate_read_feed_entry_mappings_and_count_feed_uuids() -> (
            Generator[ReadFeedEntryUserMapping, None, None]
        ):
            for feed_entry_uuid, feed_uuid in (
                FeedEntry.objects.filter(q).values_list("uuid", "feed_id").iterator()
            ):
                increment_counter.update([feed_uuid])

                yield ReadFeedEntryUserMapping(feed_entry_id=feed_entry_uuid, user=user)

        with transaction.atomic():
            created_count = bulk_create_iter(
                generate_read_feed_entry_mappings_and_count_feed_uuids(),
                ReadFeedEntryUserMapping,
            )
            if created_count > 0:
                User.objects.filter(uuid=user.uuid).update(
                    read_feed_entries_counter=(
                        F("read_feed_entries_counter") + created_count
                    )
                )

        if increment_counter:
            increment_read_in_counts_lookup_cache(user, increment_counter, cache)
            delete_read_feed_entry_uuids_cache(user, cache)

        return Response(status=204)

    @extend_schema(
        summary="Unmark multiple feed entries as 'read'",
        description="Unmark multiple feed entries as 'read'",
        request=FeedEntriesMarkSerializer,
        responses={204: OpenApiResponse(description="No response body")},
    )
    def delete(self, request: Request):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        serializer = FeedEntriesMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed_entry_uuids: frozenset[uuid_.UUID] = frozenset(
            serializer.validated_data["feed_entry_uuids"]
        )

        if len(feed_entry_uuids) < 1:
            return Response(status=204)

        increment_counter: Counter[uuid_.UUID] = Counter()

        with transaction.atomic():
            total_deleted_count = 0
            for uuid, feed_uuid in (
                ReadFeedEntryUserMapping.objects.select_related("feed_entry")
                .filter(user=user, feed_entry_id__in=feed_entry_uuids)
                .values_list("uuid", "feed_entry__feed_id")
                .iterator()
            ):
                _, deletes = ReadFeedEntryUserMapping.objects.filter(uuid=uuid).delete()
                deleted_count = deletes.get("api.ReadFeedEntryUserMapping", 0)
                if deleted_count > 0:
                    total_deleted_count += deleted_count
                    increment_counter.update([feed_uuid])

            if total_deleted_count > 0:
                User.objects.filter(uuid=user.uuid).update(
                    read_feed_entries_counter=F("read_feed_entries_counter")
                    - total_deleted_count
                )

        if increment_counter:
            increment_read_in_counts_lookup_cache(
                user,
                {feed_uuid: -incr for feed_uuid, incr in increment_counter.items()},
                cache,
            )
            delete_read_feed_entry_uuids_cache(user, cache)

        return Response(status=204)


class FeedEntryFavoriteView(APIView):
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(*args, **kwargs)

    @extend_schema(
        summary="Mark a feed entry as 'favorite'",
        description="Mark a feed entry as 'favorite'",
        request=None,
        responses={204: OpenApiResponse(description="No response body")},
    )
    def post(self, request: Request, *, uuid: uuid_.UUID):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(uuid=uuid)
        except FeedEntry.DoesNotExist:
            raise NotFound("feed entry not found")

        user.favorite_feed_entries.add(feed_entry)

        delete_favorite_feed_entry_uuids_cache(user, cache)

        return Response(status=204)

    @extend_schema(
        summary="Unmark a feed entry as 'favorite'",
        description="Unmark a feed entry as 'favorite'",
        request=None,
        responses={204: OpenApiResponse(description="No response body")},
    )
    def delete(self, request: Request, *, uuid: uuid_.UUID):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        User.favorite_feed_entries.through.objects.filter(
            user=user, feedentry_id=uuid
        ).delete()

        delete_favorite_feed_entry_uuids_cache(user, cache)

        return Response(status=204)


class FeedEntriesFavoriteView(APIView):
    @extend_schema(
        summary="Mark multiple feed entries as 'favorite'",
        description="Mark multiple feed entries as 'favorite'",
        request=FeedEntriesMarkSerializer,
        responses={204: OpenApiResponse(description="No response body")},
    )
    def post(self, request: Request):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        serializer = FeedEntriesMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed_entry_uuids: frozenset[uuid_.UUID] = frozenset(
            serializer.validated_data["feed_entry_uuids"]
        )

        if len(feed_entry_uuids) < 1:
            return Response(status=204)

        feed_entries = list(FeedEntry.objects.filter(uuid__in=feed_entry_uuids))

        if len(feed_entries) != len(feed_entry_uuids):
            raise NotFound("feed entry not found")

        user.favorite_feed_entries.add(*feed_entries)

        delete_favorite_feed_entry_uuids_cache(user, cache)

        return Response(status=204)

    @extend_schema(
        summary="Unmark multiple feed entries as 'favorite'",
        description="Unmark multiple feed entries as 'favorite'",
        request=FeedEntriesMarkSerializer,
        responses={204: OpenApiResponse(description="No response body")},
    )
    def delete(self, request: Request):
        cache: BaseCache = caches["default"]

        user = cast(User, request.user)

        serializer = FeedEntriesMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed_entry_uuids: frozenset[uuid_.UUID] = frozenset(
            serializer.validated_data["feed_entry_uuids"]
        )

        if len(feed_entry_uuids) < 1:
            return Response(status=204)

        User.favorite_feed_entries.through.objects.filter(
            user=user, feedentry_id__in=feed_entry_uuids
        ).delete()

        delete_favorite_feed_entry_uuids_cache(user, cache)

        return Response(status=204)


class FeedEntryLanguagesView(APIView):
    @extend_schema(
        summary="Get List of Languages in the system",
        description="Get List of Languages in the system",
        parameters=[FeedEntryLanguagesQuerySerializer],
        responses=FeedEntryLanguagesSerializer,
    )
    def get(self, request: Request):
        cache: BaseCache = caches["default"]

        serializer = FeedEntryLanguagesQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        kind: str = serializer.validated_data["kind"]

        cache_key = f"feed_entry_languages__{kind}"
        languages: list[str] | None = cache.get(cache_key)
        if languages is None:
            field: str
            if kind == "iso639_3":
                field = "language_id"
            elif kind == "iso639_1":
                field = "language__iso639_1"
            elif kind == "name":
                field = "language__name"
            else:  # pragma: no cover
                raise NotFound("kind not found")

            languages = list(FeedEntry.objects.values_list(field, flat=True).distinct())
            cache.set(
                cache_key,
                languages,
                _FEED_ENTRY_LANGUAGES_CACHE_TIMEOUT_SECONDS,
            )

        return Response(
            FeedEntryLanguagesSerializer(
                {
                    "languages": languages,
                }
            ).data
        )
