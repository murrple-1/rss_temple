import datetime
from typing import cast

import validators
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.signals import setting_changed
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from rest_framework import permissions, throttling
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api import query_utils
from api.exceptions import QueryException
from api.fields import FieldMap
from api.models import (
    NotifyEmailQueueEntry,
    NotifyEmailQueueEntryRecipient,
    User,
    VerificationToken,
)
from api.render import verify as verifyrender

_OBJECT_NAME = "user"


_USER_VERIFICATION_EXPIRY_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _USER_VERIFICATION_EXPIRY_INTERVAL

    _USER_VERIFICATION_EXPIRY_INTERVAL = settings.USER_VERIFICATION_EXPIRY_INTERVAL


_load_global_settings()


@api_view(["GET", "PUT"])
@permission_classes([permissions.IsAuthenticated])
def user(request: Request) -> Response:
    if request.method == "GET":
        return _user_get(request)
    elif request.method == "PUT":
        return _user_put(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST"])
@throttle_classes([throttling.UserRateThrottle])
def user_verify(request: Request) -> Response:
    if request.method == "POST":
        return _user_verify_post(request)
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
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return Response(e.message, status=e.httpcode)

    ret_obj = query_utils.generate_return_object(field_maps, user, request)

    return Response(ret_obj)


def _user_put(request: Request):
    if type(request.data) is not dict:
        raise ValidationError({".": "must be object"})  # pragma: no cover

    assert isinstance(request.data, dict)

    user = cast(User, request.user)

    has_changed = False

    verification_token: VerificationToken | None = None
    if "email" in request.data:
        if type(request.data["email"]) is not str:
            raise ValidationError({"email": "must be string"})

        if not validators.email(request.data["email"]):
            raise ValidationError({"email": "malformed"})  # pragma: no cover

        if user.email != request.data["email"]:
            if User.objects.filter(email=request.data["email"]).exists():
                return Response("email already in use", status=409)

            user.email = request.data["email"]

            verification_token = VerificationToken(
                user=user,
                expires_at=(timezone.now() + _USER_VERIFICATION_EXPIRY_INTERVAL),
            )

            has_changed = True

    if "my" in request.data:
        my_json = request.data["my"]
        if type(my_json) is not dict:
            raise ValidationError({"my": "must be object"})

        if "password" in my_json:
            password_json = my_json["password"]
            if type(password_json) is not dict:
                raise ValidationError({"my": {"password": "must be object"}})

            if "old" not in password_json:
                raise ValidationError({"my": {"password": {"old": "missing"}}})

            if type(password_json["old"]) is not str:
                raise ValidationError({"my": {"password": {"old": "must be string"}}})

            if "new" not in password_json:
                raise ValidationError({"my": {"password": {"new": "missing"}}})

            if type(password_json["new"]) is not str:
                raise ValidationError({"my": {"password": {"new": "must be string"}}})

            if not check_password(password_json["old"], user.password):
                raise PermissionDenied()

            user.set_password(password_json["new"])

            has_changed = True

    if has_changed:
        with transaction.atomic():
            user.save()

            if verification_token is not None:
                VerificationToken.objects.filter(user=user).delete()
                verification_token.save()

                token_str = verification_token.token_str()

                subject = verifyrender.subject()
                plain_text = verifyrender.plain_text(token_str)
                html_text = verifyrender.html_text(token_str)

                email_queue_entry = NotifyEmailQueueEntry.objects.create(
                    subject=subject, plain_text=plain_text, html_text=html_text
                )
                NotifyEmailQueueEntryRecipient.objects.create(
                    type=NotifyEmailQueueEntryRecipient.TYPE_TO,
                    email=request.data["email"],
                    entry=email_queue_entry,
                )

    return Response(status=204)


def _user_verify_post(request: Request):
    token = request.POST.get("token")

    if token is None:
        raise ValidationError({"token": "missing"})

    verification_token = VerificationToken.find_by_token(token)

    if verification_token is None:
        raise NotFound("token not found")

    verification_token.delete()

    return Response(status=204)


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
