import re
import uuid
from typing import Any, cast

from django.conf import settings
from django.core.cache import caches
from django.core.signals import setting_changed
from django.db import transaction
from django.db.models import OrderBy, Q
from django.dispatch import receiver
from django.http.request import HttpRequest
from django.http.response import HttpResponseBase
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api import query_utils
from api.fields import FieldMap
from api.models import FeedEntry, ReadFeedEntryUserMapping, User
from api.serializers import (
    FeedEntriesMarkGlobalSerializer,
    FeedEntriesMarkSerializer,
    GetMultipleSerializer,
    GetSingleSerializer,
    StableCreateMultipleSerializer,
    StableQueryMultipleSerializer,
)

_MAX_FEED_ENTRIES_STABLE_QUERY_COUNT: int


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _MAX_FEED_ENTRIES_STABLE_QUERY_COUNT

    _MAX_FEED_ENTRIES_STABLE_QUERY_COUNT = settings.MAX_FEED_ENTRIES_STABLE_QUERY_COUNT


_load_global_settings()

_OBJECT_NAME = "feedentry"


class FeedEntryView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        kwargs["uuid"] = uuid.UUID(kwargs["uuid"])
        return super().dispatch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Get Single Feed Entry",
        operation_description="Get Single Feed Entry",
        query_serializer=GetSingleSerializer,
    )
    def get(self, request: Request, **kwargs: Any):
        serializer = GetSingleSerializer(
            data=request.query_params,
            context={"object_name": _OBJECT_NAME, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        field_maps: list[FieldMap] = serializer.data["my_fields"]

        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
        except FeedEntry.DoesNotExist:
            raise NotFound("feed entry not found")

        ret_obj = query_utils.generate_return_object(field_maps, feed_entry, request)

        return Response(ret_obj)


class FeedEntriesQueryView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_summary="Query for Feed Entries",
        operation_description="Query for Feed Entries",
        request_body=GetMultipleSerializer,
    )
    def post(self, request: Request):
        serializer = GetMultipleSerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        count: int = serializer.data["count"]
        skip: int = serializer.data["skip"]
        sort: list[OrderBy] = serializer.data["sort"]
        search: list[Q] = serializer.get_filter_args(request)
        field_maps: list[FieldMap] = serializer.data["my_fields"]
        return_objects: bool = serializer.data["return_objects"]
        return_total_count: bool = serializer.data["return_total_count"]

        feed_entries = FeedEntry.annotate_search_vectors(
            FeedEntry.objects.all()
        ).filter(*search)

        ret_obj: dict[str, Any] = {}

        if return_objects:
            objs: list[dict[str, Any]] = []
            for feed_entry in feed_entries.order_by(*sort)[skip : skip + count]:
                obj = query_utils.generate_return_object(
                    field_maps, feed_entry, request
                )
                objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = feed_entries.count()

        return Response(ret_obj)


class FeedEntriesQueryStableCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_summary="Stable Query Creation for Feed Entries",
        operation_description="Stable Query Creation for Feed Entries",
        request_body=StableCreateMultipleSerializer,
    )
    def post(self, request: Request):
        cache = caches["stable_query"]

        serializer = StableCreateMultipleSerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        sort: list[OrderBy] = serializer.data["sort"]
        search: list[Q] = serializer.get_filter_args(request)

        token = f"feedentry-{uuid.uuid4().int}"

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
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_summary="Stable Query for Feed Entries",
        operation_description="Stable Query for Feed Entries",
        request_body=StableQueryMultipleSerializer,
    )
    def post(self, request: Request):
        cache = caches["stable_query"]

        serializer = StableQueryMultipleSerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        token: str = serializer.data["token"]
        count: int = serializer.data["count"]
        skip: int = serializer.data["skip"]
        field_maps: list[FieldMap] = serializer.data["my_fields"]
        return_objects: bool = serializer.data["return_objects"]
        return_total_count: bool = serializer.data["return_total_count"]

        cache.touch(token)
        uuids = cache.get(token, [])

        ret_obj: dict[str, Any] = {}

        if return_objects:
            current_uuids = uuids[skip : skip + count]

            feed_entries = {
                feed_entry.uuid: feed_entry
                for feed_entry in FeedEntry.objects.filter(uuid__in=current_uuids)
            }

            objs: list[dict[str, Any]] = []
            if len(current_uuids) == len(feed_entries):
                for uuid_ in current_uuids:
                    feed_entry = feed_entries[uuid_]
                    obj = query_utils.generate_return_object(
                        field_maps, feed_entry, request
                    )
                    objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = len(uuids)

        return Response(ret_obj)


class FeedEntryReadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        kwargs["uuid"] = uuid.UUID(kwargs["uuid"])
        return super().dispatch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Mark a feed entry as 'read'",
        operation_description="Mark a feed entry as 'read'",
    )
    def post(self, request: Request, **kwargs: Any):
        read_feed_entry_user_mapping: ReadFeedEntryUserMapping
        with transaction.atomic():
            feed_entry: FeedEntry
            try:
                feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
            except FeedEntry.DoesNotExist:
                raise NotFound("feed entry not found")

            ret_obj: str
            if feed_entry.is_archived:
                ret_obj = ""
            else:
                (
                    read_feed_entry_user_mapping,
                    _,
                ) = ReadFeedEntryUserMapping.objects.get_or_create(
                    feed_entry=feed_entry, user=cast(User, request.user)
                )

                ret_obj = read_feed_entry_user_mapping.read_at.isoformat()

        return Response(ret_obj)

    @swagger_auto_schema(
        operation_summary="Unmark a feed entry as 'read'",
        operation_description="Unmark a feed entry as 'read'",
    )
    def delete(self, request: Request, **kwargs: Any):
        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
        except FeedEntry.DoesNotExist:
            return Response(status=204)

        cast(User, request.user).read_feed_entries.remove(feed_entry)

        return Response(status=204)


class FeedEntriesReadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_summary="Mark multiple feed entries as 'read'",
        operation_description="Mark multiple feed entries as 'read'",
        request_body=FeedEntriesMarkGlobalSerializer,
    )
    def post(self, request: Request):
        serializer = FeedEntriesMarkGlobalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        q: Q | None = None
        if feed_uuids := serializer.data["feed_uuids"]:
            if q is None:
                q = Q(feed__uuid__in=feed_uuids)
            else:
                q |= Q(feed__uuid__in=feed_uuids)  # pragma: no cover

        if feed_entry_uuids := serializer.data["feed_entry_uuids"]:
            if q is None:
                q = Q(uuid__in=feed_entry_uuids)
            else:
                q |= Q(uuid__in=feed_entry_uuids)

        if q is None:
            raise ValidationError("no entries to mark read")

        q = Q(is_archived=False) & q

        ReadFeedEntryUserMapping.objects.bulk_create(
            [
                ReadFeedEntryUserMapping(
                    feed_entry=feed_entry, user=cast(User, request.user)
                )
                for feed_entry in FeedEntry.objects.filter(q).iterator()
            ],
            ignore_conflicts=True,
        )

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Unmark multiple feed entries as 'read'",
        operation_description="Unmark multiple feed entries as 'read'",
        request_body=FeedEntriesMarkSerializer,
    )
    def delete(self, request: Request):
        serializer = FeedEntriesMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed_entry_uuids: frozenset[uuid.UUID] = frozenset(
            serializer.data["feed_entry_uuids"]
        )

        if len(feed_entry_uuids) < 1:
            return Response(status=204)

        cast(User, request.user).read_feed_entries.filter(
            uuid__in=feed_entry_uuids
        ).delete()

        return Response(status=204)


class FeedEntryFavoriteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        kwargs["uuid"] = uuid.UUID(kwargs["uuid"])
        return super().dispatch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Mark a feed entry as 'favorite'",
        operation_description="Mark a feed entry as 'favorite'",
    )
    def post(self, request: Request, **kwargs: Any):
        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
        except FeedEntry.DoesNotExist:
            return Response("feed entry not found", status=404)

        cast(User, request.user).favorite_feed_entries.add(feed_entry)

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Unmark a feed entry as 'favorite'",
        operation_description="Unmark a feed entry as 'favorite'",
    )
    def delete(self, request: Request, **kwargs: Any):
        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
        except FeedEntry.DoesNotExist:
            return Response(status=204)

        cast(User, request.user).favorite_feed_entries.remove(feed_entry)

        return Response(status=204)


class FeedEntriesFavoriteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_summary="Mark multiple feed entries as 'favorite'",
        operation_description="Mark multiple feed entries as 'favorite'",
        request_body=FeedEntriesMarkSerializer,
    )
    def post(self, request: Request):
        serializer = FeedEntriesMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed_entry_uuids: frozenset[uuid.UUID] = frozenset(
            serializer.data["feed_entry_uuids"]
        )

        if len(feed_entry_uuids) < 1:
            return Response(status=204)

        feed_entries = list(FeedEntry.objects.filter(uuid__in=feed_entry_uuids))

        if len(feed_entries) != len(feed_entry_uuids):
            raise NotFound("feed entry not found")

        for feed_entry in feed_entries:
            cast(User, request.user).favorite_feed_entries.add(feed_entry)

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Unmark multiple feed entries as 'favorite'",
        operation_description="Unmark multiple feed entries as 'favorite'",
        request_body=FeedEntriesMarkSerializer,
    )
    def delete(self, request: Request):
        serializer = FeedEntriesMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed_entry_uuids: frozenset[uuid.UUID] = frozenset(
            serializer.data["feed_entry_uuids"]
        )

        if len(feed_entry_uuids) < 1:
            return Response(status=204)

        cast(User, request.user).favorite_feed_entries.filter(
            uuid__in=feed_entry_uuids
        ).delete()

        return Response(status=204)
