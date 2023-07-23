import itertools
import re
import uuid
from typing import Any, cast

from django.core.cache import caches
from django.db import transaction
from django.db.models import OrderBy, Q
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api import query_utils
from api.exceptions import QueryException
from api.fields import FieldMap
from api.models import FeedEntry, ReadFeedEntryUserMapping, User

_OBJECT_NAME = "feedentry"


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def feed_entry(request: Request, **kwargs: Any) -> Response:
    kwargs["uuid"] = uuid.UUID(kwargs["uuid"])

    if request.method == "GET":
        return _feed_entry_get(request, **kwargs)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def feed_entries_query(request: Request) -> Response:
    if request.method == "POST":
        return _feed_entries_query_post(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def feed_entries_query_stable_create(request: Request) -> Response:
    if request.method == "POST":
        return _feed_entries_query_stable_create_post(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def feed_entries_query_stable(request: Request) -> Response:
    if request.method == "POST":
        return _feed_entries_query_stable_post(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def feed_entry_read(request: Request, **kwargs: Any) -> Response:
    kwargs["uuid"] = uuid.UUID(kwargs["uuid"])

    if request.method == "POST":
        return _feed_entry_read_post(request, **kwargs)
    elif request.method == "DELETE":
        return _feed_entry_read_delete(request, **kwargs)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def feed_entries_read(request: Request) -> Response:
    if request.method == "POST":
        return _feed_entries_read_post(request)
    elif request.method == "DELETE":
        return _feed_entries_read_delete(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def feed_entry_favorite(request: Request, **kwargs: Any) -> Response:
    kwargs["uuid"] = uuid.UUID(kwargs["uuid"])

    if request.method == "POST":
        return _feed_entry_favorite_post(request, **kwargs)
    elif request.method == "DELETE":
        return _feed_entry_favorite_delete(request, **kwargs)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def feed_entries_favorite(request: Request) -> Response:
    if request.method == "POST":
        return _feed_entries_favorite_post(request)
    elif request.method == "DELETE":
        return _feed_entries_favorite_delete(request)
    else:  # pragma: no cover
        raise ValueError


def _feed_entry_get(request: Request, **kwargs: Any):
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


def _feed_entries_query_post(request: Request):
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

    feed_entries = FeedEntry.annotate_search_vectors(FeedEntry.objects.all()).filter(
        *search
    )

    ret_obj: dict[str, Any] = {}

    if return_objects:
        objs: list[dict[str, Any]] = []
        for feed_entry in feed_entries.order_by(*sort)[skip : skip + count]:
            obj = query_utils.generate_return_object(field_maps, feed_entry, request)
            objs.append(obj)

        ret_obj["objects"] = objs

    if return_total_count:
        ret_obj["totalCount"] = feed_entries.count()

    return Response(ret_obj)


def _feed_entries_query_stable_create_post(request: Request):
    cache = caches["stable_query"]

    if type(request.data) is not dict:
        raise ValidationError({".": "must be object"})  # pragma: no cover

    assert isinstance(request.data, dict)

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
            .values_list("uuid", flat=True)
        ),
    )

    return Response(token)


def _feed_entries_query_stable_post(request: Request):
    cache = caches["stable_query"]

    if type(request.data) is not dict:
        raise ValidationError({".": "must be object"})  # pragma: no cover

    assert isinstance(request.data, dict)

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


def _feed_entry_read_post(request: Request, **kwargs: Any):
    read_feed_entry_user_mapping: ReadFeedEntryUserMapping
    with transaction.atomic():
        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
        except FeedEntry.DoesNotExist:
            raise NotFound("feed entry not found")

        (
            read_feed_entry_user_mapping,
            _,
        ) = ReadFeedEntryUserMapping.objects.get_or_create(
            feed_entry=feed_entry, user=cast(User, request.user)
        )

    ret_obj = read_feed_entry_user_mapping.read_at.isoformat()

    return Response(ret_obj)


def _feed_entry_read_delete(request: Request, **kwargs: Any):
    cast(User, request.user).read_feed_entries.clear()
    return Response(status=204)


def _feed_entries_read_post(request: Request):
    if type(request.data) is not dict:
        raise ValidationError({".": "must be array"})  # pragma: no cover

    assert isinstance(request.data, dict)

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

    batch_size = 768
    objs = (
        ReadFeedEntryUserMapping(feed_entry=feed_entry, user=cast(User, request.user))
        for feed_entry in FeedEntry.objects.filter(q).iterator()
    )
    with transaction.atomic():
        while True:
            batch = list(itertools.islice(objs, batch_size))
            if not batch:
                break
            ReadFeedEntryUserMapping.objects.bulk_create(batch, ignore_conflicts=True)

    return Response(status=204)


def _feed_entries_read_delete(request: Request):
    if type(request.data) is not list:
        raise ValidationError({".": "must be array"})  # pragma: no cover

    assert isinstance(request.data, list)

    if len(request.data) < 1:
        return Response(status=204)

    _ids: frozenset[uuid.UUID]
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in request.data)
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({".[]": "uuid malformed"})

    cast(User, request.user).read_feed_entries.filter(uuid__in=_ids).delete()

    return Response(status=204)


def _feed_entry_favorite_post(request: Request, **kwargs: Any):
    feed_entry: FeedEntry
    try:
        feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
    except FeedEntry.DoesNotExist:
        return Response("feed entry not found", status=404)

    cast(User, request.user).favorite_feed_entries.add(feed_entry)

    return Response(status=204)


def _feed_entry_favorite_delete(request: Request, **kwargs: Any):
    feed_entry: FeedEntry
    try:
        feed_entry = FeedEntry.objects.get(uuid=kwargs["uuid"])
    except FeedEntry.DoesNotExist:
        return Response(status=204)

    cast(User, request.user).favorite_feed_entries.remove(feed_entry)

    return Response(status=204)


def _feed_entries_favorite_post(request: Request):
    if type(request.data) is not list:
        raise ValidationError({".": "must be array"})  # pragma: no cover

    assert isinstance(request.data, list)

    if len(request.data) < 1:
        return Response(status=204)

    _ids: frozenset[uuid.UUID]
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in request.data)
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({".[]": "uuid malformed"})

    feed_entries = list(FeedEntry.objects.filter(uuid__in=_ids))

    if len(feed_entries) != len(_ids):
        raise NotFound("feed entry not found")

    for feed_entry in feed_entries:
        cast(User, request.user).favorite_feed_entries.add(feed_entry)

    return Response(status=204)


def _feed_entries_favorite_delete(request: Request):
    if type(request.data) is not list:
        return Response("JSON body must be array", status=400)  # pragma: no cover

    assert isinstance(request.data, list)

    if len(request.data) < 1:
        return Response(status=204)

    _ids: frozenset[uuid.UUID]
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in request.data)
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({".[]": "uuid malformed"})

    cast(User, request.user).favorite_feed_entries.filter(uuid__in=_ids).delete()

    return Response(status=204)
