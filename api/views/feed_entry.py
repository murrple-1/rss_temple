import datetime
import itertools
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
from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api import query_utils
from api.exceptions import QueryException
from api.fields import FieldMap
from api.models import FeedEntry, ReadFeedEntryUserMapping, User

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

    def get(self, request: Request, **kwargs: Any):
        field_maps: list[FieldMap]
        try:
            fields = query_utils.get_fields__query_dict(request.query_params)
            field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
        except QueryException as e:  # pragma: no cover
            return Response(e.message, status=e.httpcode)

        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
        except FeedEntry.DoesNotExist:
            raise NotFound("feed entry not found")

        ret_obj = query_utils.generate_return_object(field_maps, feed_entry, request)

        return Response(ret_obj)


class FeedEntriesQueryView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request: Request):
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

    def post(self, request: Request):
        cache = caches["stable_query"]

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

    def post(self, request: Request):
        cache = caches["stable_query"]

        token: str
        try:
            token = request.data["token"]
        except KeyError:
            raise ValidationError({"token": "missing"})

        if type(token) is not str:
            raise ValidationError({"token": "must be string"})

        if re.search(r"^feedentry-\d+$", token) is None:
            raise ValidationError({"token": "malformed"})

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

    def post(self, request: Request):
        q: Q | None = None

        if "feedUuids" in request.data:
            if type(request.data["feedUuids"]) is not list:
                raise ValidationError({"feedUuids": "must be array"})

            feed_uuids = set()
            for feed_uuid_str in request.data["feedUuids"]:
                if type(feed_uuid_str) is not str:
                    raise ValidationError({"feedUuids[]": "must be string"})

                try:
                    feed_uuids.add(uuid.UUID(feed_uuid_str))
                except ValueError:
                    raise ValidationError({"feedUuids[]": "malformed"})

            if q is None:
                q = Q(feed__uuid__in=feed_uuids)
            else:
                q |= Q(feed__uuid__in=feed_uuids)  # pragma: no cover

        if "feedEntryUuids" in request.data:
            if type(request.data["feedEntryUuids"]) is not list:
                raise ValidationError({"feedEntryUuids": "must be array"})

            feed_entry_uuids = set()
            for feed_entry_uuid_str in request.data["feedEntryUuids"]:
                if type(feed_entry_uuid_str) is not str:
                    raise ValidationError({"feedEntryUuids[]": "must be string"})

                try:
                    feed_entry_uuids.add(uuid.UUID(feed_entry_uuid_str))
                except ValueError:
                    raise ValidationError({"feedEntryUuids[]": "malformed"})

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

    def delete(self, request: Request):
        if "feedEntryUuids" not in request.data:
            raise ValidationError({"feedEntryUuids": "missing"})

        feed_entry_uuid_strs = request.data["feedEntryUuids"]

        if type(feed_entry_uuid_strs) is not list:
            raise ValidationError({"feedEntryUuids": "must be array"})

        if len(request.data) < 1:
            return Response(status=204)

        _ids: frozenset[uuid.UUID]
        try:
            _ids = frozenset(uuid.UUID(uuid_) for uuid_ in feed_entry_uuid_strs)
        except (ValueError, TypeError, AttributeError):
            raise ValidationError({".[]": "uuid malformed"})

        cast(User, request.user).read_feed_entries.filter(uuid__in=_ids).delete()

        return Response(status=204)


class FeedEntryFavoriteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        kwargs["uuid"] = uuid.UUID(kwargs["uuid"])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request: Request, **kwargs: Any):
        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
        except FeedEntry.DoesNotExist:
            return Response("feed entry not found", status=404)

        cast(User, request.user).favorite_feed_entries.add(feed_entry)

        return Response(status=204)

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

    def post(self, request: Request):
        if "feedEntryUuids" not in request.data:
            raise ValidationError({"feedEntryUuids": "missing"})

        feed_entry_uuid_strs = request.data["feedEntryUuids"]
        if type(feed_entry_uuid_strs) is not list:
            raise ValidationError({"feedEntryUuids": "must be array"})

        if len(feed_entry_uuid_strs) < 1:
            return Response(status=204)

        _ids: frozenset[uuid.UUID]
        try:
            _ids = frozenset(uuid.UUID(uuid_) for uuid_ in feed_entry_uuid_strs)
        except (ValueError, TypeError, AttributeError):
            raise ValidationError({"feedEntryUuids[]": "uuid malformed"})

        feed_entries = list(FeedEntry.objects.filter(uuid__in=_ids))

        if len(feed_entries) != len(_ids):
            raise NotFound("feed entry not found")

        for feed_entry in feed_entries:
            cast(User, request.user).favorite_feed_entries.add(feed_entry)

        return Response(status=204)

    def delete(self, request: Request):
        if "feedEntryUuids" not in request.data:
            raise ValidationError({"feedEntryUuids": "missing"})

        feed_entry_uuid_strs = request.data["feedEntryUuids"]
        if type(feed_entry_uuid_strs) is not list:
            raise ValidationError({"feedEntryUuids": "must be array"})

        if len(feed_entry_uuid_strs) < 1:
            return Response(status=204)

        _ids: frozenset[uuid.UUID]
        try:
            _ids = frozenset(uuid.UUID(uuid_) for uuid_ in feed_entry_uuid_strs)
        except (ValueError, TypeError, AttributeError):
            raise ValidationError({".[]": "uuid malformed"})

        cast(User, request.user).favorite_feed_entries.filter(uuid__in=_ids).delete()

        return Response(status=204)
