import datetime

from django.conf import settings
from django.core.signals import setting_changed
from django.db import transaction
from django.dispatch import receiver
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseBase,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)
from django.utils import timezone
from throttle.decorators import throttle

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


@throttle(zone="default")
def passwordresettoken_request(request: HttpRequest) -> HttpResponseBase:
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _passwordresettoken_request_post(request)
    else:  # pragma: no cover
        raise ValueError


@throttle(zone="default")
def passwordresettoken_reset(request: HttpRequest) -> HttpResponseBase:
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _passwordresettoken_reset_post(request)
    else:  # pragma: no cover
        raise ValueError


def _passwordresettoken_request_post(request: HttpRequest):
    email = request.POST.get("email")

    if email is None:
        return HttpResponseBadRequest("'email' missing")

    user: User
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return HttpResponse(status=204)

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

    return HttpResponse(status=204)


def _passwordresettoken_reset_post(request: HttpRequest):
    token = request.POST.get("token")
    if token is None:
        return HttpResponseBadRequest("'token' missing")

    password = request.POST.get("password")
    if password is None:
        return HttpResponseBadRequest("'password' missing")

    password_reset_token = PasswordResetToken.find_by_token(token)

    if password_reset_token is None:
        return HttpResponseNotFound("token not valid")

    with transaction.atomic():
        password_reset_token.user.set_password(password)

        password_reset_token.delete()

    return HttpResponse(status=204)
