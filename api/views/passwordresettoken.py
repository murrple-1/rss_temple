import datetime

from django.conf import settings
from django.core.signals import setting_changed
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from rest_framework import throttling
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import (
    NotifyEmailQueueEntry,
    NotifyEmailQueueEntryRecipient,
    PasswordResetToken,
    User,
)
from api.render import passwordreset as passwordresetrender

_PASSWORDRESETTOKEN_EXPIRY_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _PASSWORDRESETTOKEN_EXPIRY_INTERVAL

    _PASSWORDRESETTOKEN_EXPIRY_INTERVAL = settings.PASSWORDRESETTOKEN_EXPIRY_INTERVAL


_load_global_settings()


@api_view(["POST"])
@throttle_classes([throttling.UserRateThrottle])
def passwordresettoken_request(request: Request) -> Response:
    if request.method == "POST":
        return _passwordresettoken_request_post(request)
    else:  # pragma: no cover
        raise ValueError


@api_view(["POST"])
@throttle_classes([throttling.UserRateThrottle])
def passwordresettoken_reset(request: Request) -> Response:
    if request.method == "POST":
        return _passwordresettoken_reset_post(request)
    else:  # pragma: no cover
        raise ValueError


def _passwordresettoken_request_post(request: Request):
    email = request.POST.get("email")

    if email is None:
        raise ValidationError({"email": "missing"})

    user: User
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return Response(status=204)

    password_reset_token = PasswordResetToken(
        user=user,
        expires_at=(timezone.now() + _PASSWORDRESETTOKEN_EXPIRY_INTERVAL),
    )

    with transaction.atomic():
        PasswordResetToken.objects.filter(user=user).delete()
        password_reset_token.save()

        token_str = password_reset_token.token_str()

        subject = passwordresetrender.subject()
        plain_text = passwordresetrender.plain_text(token_str)
        html_text = passwordresetrender.html_text(token_str)

        email_queue_entry = NotifyEmailQueueEntry.objects.create(
            subject=subject, plain_text=plain_text, html_text=html_text
        )
        NotifyEmailQueueEntryRecipient.objects.create(
            type=NotifyEmailQueueEntryRecipient.TYPE_TO,
            email=email,
            entry=email_queue_entry,
        )

    return Response(status=204)


def _passwordresettoken_reset_post(request: Request):
    token = request.POST.get("token")
    if token is None:
        raise ValidationError({"token": "missing"})

    password = request.POST.get("password")
    if password is None:
        raise ValidationError({"token": "missing"})

    password_reset_token = PasswordResetToken.find_by_token(token)

    if password_reset_token is None:
        raise NotFound("token not valid")

    with transaction.atomic():
        password_reset_token.user.set_password(password)

        password_reset_token.delete()

    return Response(status=204)
