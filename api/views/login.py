import datetime

import validators
from django.conf import settings
from django.core.signals import setting_changed
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from knox.views import LoginView as KnoxLoginView
from rest_framework import authentication, throttling
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import (
    NotifyEmailQueueEntry,
    NotifyEmailQueueEntryRecipient,
    User,
    VerificationToken,
)
from api.render import verify as verifyrender

_USER_VERIFICATION_EXPIRY_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _USER_VERIFICATION_EXPIRY_INTERVAL

    _USER_VERIFICATION_EXPIRY_INTERVAL = settings.USER_VERIFICATION_EXPIRY_INTERVAL


_load_global_settings()


class LoginView(KnoxLoginView):
    authentication_classes = [authentication.BasicAuthentication]
    throttle_classes = [throttling.UserRateThrottle]


@api_view(["POST"])
@throttle_classes([throttling.UserRateThrottle])
def my_login(request: Request) -> Response:
    if request.method == "POST":
        return _my_login_post(request)
    else:  # pragma: no cover
        raise ValueError


def _prepare_verify_notification(token_str: str, email: str):
    subject = verifyrender.subject()
    plain_text = verifyrender.plain_text(token_str)
    html_text = verifyrender.html_text(token_str)

    email_queue_entry = NotifyEmailQueueEntry.objects.create(
        subject=subject, plain_text=plain_text, html_text=html_text
    )
    NotifyEmailQueueEntryRecipient.objects.create(
        type=NotifyEmailQueueEntryRecipient.TYPE_TO,
        email=email,
        entry=email_queue_entry,
    )


def _my_login_post(request: Request):
    if type(request.data) is not dict:
        raise ValidationError({".": "must be object"})  # pragma: no cover

    assert isinstance(request.data, dict)

    if "email" not in request.data:
        raise ValidationError({"email": "missing"})

    if type(request.data["email"]) is not str:
        raise ValidationError({"email": "must be string"})

    if not validators.email(request.data["email"]):
        raise ValidationError({"email": "malformed"})

    if "password" not in request.data:
        raise ValidationError({"password": "missing"})

    if type(request.data["password"]) is not str:
        raise ValidationError({"password": "must be string"})

    if User.objects.filter(email__iexact=request.data["email"]).exists():
        return Response("login already exists", status=409)

    with transaction.atomic():
        user = User.objects.create_user(request.data["email"], request.data["password"])

        verification_token = VerificationToken.objects.create(
            user=user,
            expires_at=(timezone.now() + _USER_VERIFICATION_EXPIRY_INTERVAL),
        )

        _prepare_verify_notification(
            verification_token.token_str(), request.data["email"]
        )

    return Response(status=204)
