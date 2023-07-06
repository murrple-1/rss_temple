import uuid
from typing import Any, cast

from django.db import IntegrityError, transaction
from django.db.models import OrderBy, Q
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api import query_utils
from api.exceptions import QueryException
from api.fields import FieldMap
from api.models import Feed, User, UserCategory

_OBJECT_NAME = "usercategory"


@api_view(["GET", "POST", "PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def user_category(request: Request, uuid_: str | None) -> Response:
    if uuid_ is not None:
        uuid__ = uuid.UUID(uuid_)

        if request.method == "GET":
            return _user_category_get(request, uuid__)
        elif request.method == "PUT":
            return _user_category_put(request, uuid__)
        elif request.method == "DELETE":
            return _user_category_delete(request, uuid__)
        elif request.method == "POST":
            return Response(status=204)
        else:  # pragma: no cover
            raise ValueError
    else:
        if request.method == "POST":
            return _user_category_post(request)
        elif request.method in ("GET", "PUT", "DELETE"):
            return Response(status=204)
        else:  # pragma: no cover
            raise ValueError


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def user_categories_query(request: Request) -> Response:
    if request.method == "POST":
        return _user_categories_query_post(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["PUT"])
@permission_classes([permissions.IsAuthenticated])
def user_categories_apply(request: Request) -> Response:
    if request.method == "PUT":
        return _user_categories_apply_put(request)
    else:  # pragma: no cover
        raise ValueError


def _user_category_get(request: Request, uuid_: uuid.UUID):
    field_maps: list[FieldMap]
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    user_category: UserCategory
    try:
        user_category = UserCategory.objects.get(
            uuid=uuid_, user=cast(User, request.user)
        )
    except UserCategory.DoesNotExist:
        return Response("user category not found", status=404)

    ret_obj = query_utils.generate_return_object(field_maps, user_category, request)

    return Response(ret_obj)


def _user_category_post(request: Request):
    field_maps: list[FieldMap]
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    if type(request.data) is not dict:
        return Response("JSON body must be object", status=400)  # pragma: no cover

    assert isinstance(request.data, dict)

    if "text" not in request.data:
        return Response("'text' missing", status=400)

    if type(request.data["text"]) is not str:
        return Response("'text' must be string", status=400)

    user_category = UserCategory(
        user=cast(User, request.user), text=request.data["text"]
    )

    try:
        user_category.save()
    except IntegrityError:
        return Response("user category already exists", status=409)

    ret_obj = query_utils.generate_return_object(field_maps, user_category, request)

    return Response(ret_obj)


def _user_category_put(request: Request, uuid_: uuid.UUID):
    if type(request.data) is not dict:
        return Response("JSON body must be object", status=400)  # pragma: no cover

    assert isinstance(request.data, dict)

    user_category: UserCategory
    try:
        user_category = UserCategory.objects.get(
            uuid=uuid_, user=cast(User, request.user)
        )
    except UserCategory.DoesNotExist:
        return Response("user category not found", status=404)

    has_changed = False

    if "text" in request.data:
        if type(request.data["text"]) is not str:
            return Response("'text' must be string", status=400)

        user_category.text = request.data["text"]
        has_changed = True

    if has_changed:
        try:
            user_category.save()
        except IntegrityError:
            return Response("user category already exists", status=409)

    return Response(status=204)


def _user_category_delete(request: Request, uuid_: uuid.UUID):
    count, _ = UserCategory.objects.filter(
        uuid=uuid_, user=cast(User, request.user)
    ).delete()

    if count < 1:
        raise NotFound("user category not found")

    return Response(status=204)


def _user_categories_query_post(request: Request):
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
        search = [Q(user=cast(User, request.user))] + query_utils.get_search(
            request, request.data, _OBJECT_NAME
        )
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

    user_categories = UserCategory.objects.filter(*search)

    ret_obj: dict[str, Any] = {}

    if return_objects:
        objs: list[dict[str, Any]] = []
        for user_category in user_categories.order_by(*sort)[skip : skip + count]:
            obj = query_utils.generate_return_object(field_maps, user_category, request)
            objs.append(obj)

        ret_obj["objects"] = objs

    if return_total_count:
        ret_obj["totalCount"] = user_categories.count()

    return Response(ret_obj)


def _user_categories_apply_put(request: Request):
    if type(request.data) is not dict:
        raise ValidationError({".": "must be object"})  # pragma: no cover

    assert isinstance(request.data, dict)

    all_feed_uuids: set[uuid.UUID] = set()
    all_user_category_uuids: set[uuid.UUID] = set()

    mappings: dict[uuid.UUID, frozenset[uuid.UUID]] = {}

    for feed_uuid, user_category_uuids in request.data.items():
        feed_uuid_: uuid.UUID
        try:
            feed_uuid_ = uuid.UUID(feed_uuid)
        except ValueError:
            raise ValidationError({".[]": "key malformed"})

        all_feed_uuids.add(feed_uuid_)

        if type(user_category_uuids) is not list:
            raise ValidationError({".[]": "must be array"})

        try:
            user_category_uuids = frozenset(uuid.UUID(s) for s in user_category_uuids)
        except (ValueError, TypeError):
            raise ValidationError({".[]": "malformed"})

        all_user_category_uuids.update(user_category_uuids)

        mappings[feed_uuid_] = user_category_uuids

    feeds = {feed.uuid: feed for feed in Feed.objects.filter(uuid__in=all_feed_uuids)}

    if len(feeds) < len(all_feed_uuids):
        raise NotFound("feed not found")

    user_categories = {
        user_category.uuid: user_category
        for user_category in UserCategory.objects.filter(
            uuid__in=all_user_category_uuids, user=cast(User, request.user)
        )
    }

    if len(user_categories) < len(all_user_category_uuids):
        raise NotFound("user category not found")

    with transaction.atomic():
        for feed_uuid_, user_category_uuids in mappings.items():
            feed = feeds[feed_uuid_]
            feed.user_categories.clear()

            feed.user_categories.add(
                *(
                    user_categories[user_category_uuid]
                    for user_category_uuid in user_category_uuids
                )
            )

    return Response(status=204)
