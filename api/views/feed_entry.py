import uuid as uuid_
from typing import Any, cast

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.core.signals import setting_changed
from django.db import transaction
from django.db.models import F, OrderBy, Q
from django.dispatch import receiver
from django.http.response import HttpResponseBase
from drf_yasg.utils import swagger_auto_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api import fields as fieldutils
from api.django_extensions import bulk_create_iter
from api.fields import FieldMap
from api.models import FeedEntry, ReadFeedEntryUserMapping, User
from api.serializers import (
    FeedEntriesMarkReadSerializer,
    FeedEntriesMarkSerializer,
    FeedEntryLanguagesQuerySerializer,
    FeedEntryLanguagesSerializer,
    GetManySerializer,
    GetSingleSerializer,
    StableQueryCreateSerializer,
    StableQueryMultipleSerializer,
)

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
    def dispatch(self, request: Request, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Get Single Feed Entry",
        operation_description="Get Single Feed Entry",
        query_serializer=GetSingleSerializer,
    )
    def get(self, request: Request, uuid: uuid_.UUID):
        serializer = GetSingleSerializer(
            data=request.query_params,
            context={"object_name": _OBJECT_NAME, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        field_maps: list[FieldMap] = serializer.validated_data["fields"]

        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.select_related("language").get(uuid=uuid)
        except FeedEntry.DoesNotExist:
            raise NotFound("feed entry not found")

        ret_obj = fieldutils.generate_return_object(field_maps, feed_entry, request)

        return Response(ret_obj)


class FeedEntriesQueryView(APIView):
    @swagger_auto_schema(
        operation_summary="Query for Feed Entries",
        operation_description="Query for Feed Entries",
        request_body=GetManySerializer,
    )
    def post(self, request: Request):
        serializer = GetManySerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        count: int = serializer.validated_data["count"]
        skip: int = serializer.validated_data["skip"]
        sort: list[OrderBy] = serializer.validated_data["sort"]
        search: list[Q] = serializer.validated_data["search"]
        field_maps: list[FieldMap] = serializer.validated_data["fields"]
        return_objects: bool = serializer.validated_data["return_objects"]
        return_total_count: bool = serializer.validated_data["return_total_count"]

        feed_entries = (
            FeedEntry.annotate_search_vectors(FeedEntry.objects.all())
            .filter(*search)
            .select_related("language")
        )

        ret_obj: dict[str, Any] = {}

        if return_objects:
            objs: list[dict[str, Any]] = []
            for feed_entry in feed_entries.order_by(*sort)[skip : skip + count]:
                obj = fieldutils.generate_return_object(field_maps, feed_entry, request)
                objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = feed_entries.count()

        return Response(ret_obj)


class FeedEntriesQueryStableCreateView(APIView):
    @swagger_auto_schema(
        operation_summary="Stable Query Creation for Feed Entries",
        operation_description="Stable Query Creation for Feed Entries",
        request_body=StableQueryCreateSerializer,
    )
    def post(self, request: Request):
        cache: BaseCache = caches["stable_query"]

        serializer = StableQueryCreateSerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        sort: list[OrderBy] = serializer.validated_data["sort"]
        search: list[Q] = serializer.validated_data["search"]

        token = f"feedentry-{uuid_.uuid4().int}"

        cache.set(
            token,
            list(
                FeedEntry.annotate_search_vectors(FeedEntry.objects.all())
                .filter(*search)
                .order_by(*sort)
                .values_list("uuid", flat=True)[:_MAX_FEED_ENTRIES_STABLE_QUERY_COUNT]
            ),
        )

        return Response(token)


class FeedEntriesQueryStableView(APIView):
    @swagger_auto_schema(
        operation_summary="Stable Query for Feed Entries",
        operation_description="Stable Query for Feed Entries",
        request_body=StableQueryMultipleSerializer,
    )
    def post(self, request: Request):
        cache: BaseCache = caches["stable_query"]

        serializer = StableQueryMultipleSerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        token: str = serializer.validated_data["token"]
        count: int = serializer.validated_data["count"]
        skip: int = serializer.validated_data["skip"]
        field_maps: list[FieldMap] = serializer.validated_data["fields"]
        return_objects: bool = serializer.validated_data["return_objects"]
        return_total_count: bool = serializer.validated_data["return_total_count"]

        cache.touch(token)
        uuids = cache.get(token, [])

        ret_obj: dict[str, Any] = {}

        if return_objects:
            current_uuids = uuids[skip : skip + count]

            feed_entries = {
                feed_entry.uuid: feed_entry
                for feed_entry in FeedEntry.objects.filter(
                    uuid__in=current_uuids
                ).select_related("language")
            }

            objs: list[dict[str, Any]] = []
            if len(current_uuids) == len(feed_entries):
                for uuid_ in current_uuids:
                    feed_entry = feed_entries[uuid_]
                    obj = fieldutils.generate_return_object(
                        field_maps, feed_entry, request
                    )
                    objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = len(uuids)

        return Response(ret_obj)


class FeedEntryReadView(APIView):
    def dispatch(self, request: Request, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Mark a feed entry as 'read'",
        operation_description="Mark a feed entry as 'read'",
    )
    def post(self, request: Request, *, uuid: uuid_.UUID):
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

        return Response(ret_obj)

    @swagger_auto_schema(
        operation_summary="Unmark a feed entry as 'read'",
        operation_description="Unmark a feed entry as 'read'",
    )
    def delete(self, request: Request, *, uuid: uuid_.UUID):
        user = cast(User, request.user)

        with transaction.atomic():
            _, deletes = ReadFeedEntryUserMapping.objects.filter(
                user=user, feed_entry_id=uuid
            ).delete()
            deleted_count = deletes.get("api.ReadFeedEntryUserMapping", 0)
            if deleted_count > 0:
                User.objects.filter(uuid=user.uuid).update(
                    read_feed_entries_counter=F("read_feed_entries_counter")
                    - deleted_count
                )

        return Response(status=204)


class FeedEntriesReadView(APIView):
    @swagger_auto_schema(
        operation_summary="Mark multiple feed entries as 'read'",
        operation_description="Mark multiple feed entries as 'read'",
        request_body=FeedEntriesMarkReadSerializer,
    )
    def post(self, request: Request):
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

        with transaction.atomic():
            created_count = bulk_create_iter(
                (
                    ReadFeedEntryUserMapping(feed_entry_id=feed_entry_uuid, user=user)
                    for feed_entry_uuid in FeedEntry.objects.filter(q)
                    .values_list("uuid", flat=True)
                    .iterator()
                ),
                ReadFeedEntryUserMapping,
            )
            if created_count > 0:
                User.objects.filter(uuid=user.uuid).update(
                    read_feed_entries_counter=(
                        F("read_feed_entries_counter") + created_count
                    )
                )

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Unmark multiple feed entries as 'read'",
        operation_description="Unmark multiple feed entries as 'read'",
        request_body=FeedEntriesMarkSerializer,
    )
    def delete(self, request: Request):
        user = cast(User, request.user)

        serializer = FeedEntriesMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed_entry_uuids: frozenset[uuid_.UUID] = frozenset(
            serializer.validated_data["feed_entry_uuids"]
        )

        if len(feed_entry_uuids) < 1:
            return Response(status=204)

        with transaction.atomic():
            _, deletes = ReadFeedEntryUserMapping.objects.filter(
                user=user, feed_entry_id__in=feed_entry_uuids
            ).delete()
            deleted_count = deletes.get("api.ReadFeedEntryUserMapping", 0)
            if deleted_count > 0:
                User.objects.filter(uuid=user.uuid).update(
                    read_feed_entries_counter=F("read_feed_entries_counter")
                    - deleted_count
                )

        return Response(status=204)


class FeedEntryFavoriteView(APIView):
    def dispatch(self, request: Request, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Mark a feed entry as 'favorite'",
        operation_description="Mark a feed entry as 'favorite'",
    )
    def post(self, request: Request, *, uuid: uuid_.UUID):
        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(uuid=uuid)
        except FeedEntry.DoesNotExist:
            raise NotFound("feed entry not found")

        cast(User, request.user).favorite_feed_entries.add(feed_entry)

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Unmark a feed entry as 'favorite'",
        operation_description="Unmark a feed entry as 'favorite'",
    )
    def delete(self, request: Request, *, uuid: uuid_.UUID):
        User.favorite_feed_entries.through.objects.filter(
            user=cast(User, request.user), feedentry_id=uuid
        ).delete()

        return Response(status=204)


class FeedEntriesFavoriteView(APIView):
    @swagger_auto_schema(
        operation_summary="Mark multiple feed entries as 'favorite'",
        operation_description="Mark multiple feed entries as 'favorite'",
        request_body=FeedEntriesMarkSerializer,
    )
    def post(self, request: Request):
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

        cast(User, request.user).favorite_feed_entries.add(*feed_entries)

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Unmark multiple feed entries as 'favorite'",
        operation_description="Unmark multiple feed entries as 'favorite'",
        request_body=FeedEntriesMarkSerializer,
    )
    def delete(self, request: Request):
        serializer = FeedEntriesMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed_entry_uuids: frozenset[uuid_.UUID] = frozenset(
            serializer.validated_data["feed_entry_uuids"]
        )

        if len(feed_entry_uuids) < 1:
            return Response(status=204)

        User.favorite_feed_entries.through.objects.filter(
            user=cast(User, request.user), feedentry_id__in=feed_entry_uuids
        ).delete()

        return Response(status=204)


class FeedEntryLanguagesView(APIView):
    @swagger_auto_schema(
        operation_summary="Get List of Languages in the system",
        operation_description="Get List of Languages in the system",
        query_serializer=FeedEntryLanguagesQuerySerializer,
        responses={200: FeedEntryLanguagesSerializer},
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

            languages = [
                l for l in FeedEntry.objects.values_list(field, flat=True).distinct()
            ]
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
