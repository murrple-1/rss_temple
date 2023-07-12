from typing import cast

from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api import query_utils
from api.exceptions import QueryException
from api.fields import FieldMap
from api.models import User

_OBJECT_NAME = "user"


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def user(request: Request) -> Response:
    if request.method == "GET":
        return _user_get(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["PUT"])
@permission_classes([permissions.IsAuthenticated])
def user_attributes(request: Request) -> Response:
    if request.method == "PUT":
        return _user_attributes_put(request)
    else:  # pragma: no cover
        raise ValueError


def _user_get(request: Request):
    user = request.user

    field_maps: list[FieldMap]
    try:
        fields = query_utils.get_fields__query_dict(request.query_params)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    ret_obj = query_utils.generate_return_object(field_maps, user, request)

    return Response(ret_obj)


def _user_attributes_put(request: Request):
    if type(request.data) is not dict:
        raise ValidationError({".": "must be object"})  # pragma: no cover

    assert isinstance(request.data, dict)

    user = cast(User, request.user)

    user.attributes.update(request.data)

    del_keys = set()
    for key, value in user.attributes.items():
        if value is None:
            del_keys.add(key)

    for key in del_keys:
        del user.attributes[key]

    user.save(update_fields=["attributes"])

    return Response(status=204)
