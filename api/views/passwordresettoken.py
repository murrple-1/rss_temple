import datetime

from django.conf import settings
from django.core.signals import setting_changed
from django.db import transaction
from django.dispatch import receiver
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)

from api import models
from api.password_hasher import password_hasher
from api.render import passwordreset as passwordresetrender

_PASSWORDRESETTOKEN_EXPIRY_INTERVAL = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _PASSWORDRESETTOKEN_EXPIRY_INTERVAL

    _PASSWORDRESETTOKEN_EXPIRY_INTERVAL = settings.PASSWORDRESETTOKEN_EXPIRY_INTERVAL


_load_global_settings()


def passwordresettoken_request(request):
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _passwordresettoken_request_post(request)


def passwordresettoken_reset(request):
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _passwordresettoken_reset_post(request)


def _passwordresettoken_request_post(request):
    email = request.POST.get("email")

    if email is None:
        return HttpResponseBadRequest("'email' missing")

    user = None
    try:
        user = models.User.objects.get(email__iexact=email)
    except models.User.DoesNotExist:
        return HttpResponse(status=204)

    password_reset_token = models.PasswordResetToken(
        user=user,
        expires_at=(
            datetime.datetime.now(datetime.timezone.utc)
            + _PASSWORDRESETTOKEN_EXPIRY_INTERVAL
        ),
    )

    with transaction.atomic():
        models.PasswordResetToken.objects.filter(user=user).delete()
        password_reset_token.save()

        token_str = password_reset_token.token_str()

        subject = passwordresetrender.subject()
        plain_text = passwordresetrender.plain_text(token_str)
        html_text = passwordresetrender.html_text(token_str)

        email_queue_entry = models.NotifyEmailQueueEntry.objects.create(
            subject=subject, plain_text=plain_text, html_text=html_text
        )
        models.NotifyEmailQueueEntryRecipient.objects.create(
            type=models.NotifyEmailQueueEntryRecipient.TYPE_TO,
            email=email,
            entry=email_queue_entry,
        )

    return HttpResponse(status=204)


def _passwordresettoken_reset_post(request):
    token = request.POST.get("token")
    if token is None:
        return HttpResponseBadRequest("'token' missing")

    password = request.POST.get("password")
    if password is None:
        return HttpResponseBadRequest("'password' missing")

    password_reset_token = models.PasswordResetToken.find_by_token(token)

    if password_reset_token is None:
        return HttpResponseNotFound("token not valid")

    my_login = models.MyLogin.objects.get(user_id=password_reset_token.user_id)

    my_login.pw_hash = password_hasher().hash(password)

    with transaction.atomic():
        my_login.save(update_fields=["pw_hash"])

        password_reset_token.delete()

    return HttpResponse(status=204)
