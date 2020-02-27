import datetime

from django.conf import settings
from django.dispatch import receiver
from django.core.signals import setting_changed
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseNotFound
from django.db import transaction

from api import models
from api.password_hasher import password_hasher


_PASSWORDRESETTOKEN_EXPIRY_INTERVAL = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _PASSWORDRESETTOKEN_EXPIRY_INTERVAL

    _PASSWORDRESETTOKEN_EXPIRY_INTERVAL = settings.PASSWORDRESETTOKEN_EXPIRY_INTERVAL


_load_global_settings()


def passwordresettoken_request(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _passwordresettoken_request_post(request)


def passwordresettoken_reset(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _passwordresettoken_reset_post(request)


def _passwordresettoken_request_post(request):
    email = request.POST.get('email')

    if email is None:
        return HttpResponseBadRequest('\'email\' missing')

    user = None
    try:
        user = models.User.objects.get(email=email)
    except models.User.DoesNotExist:
        return HttpResponse()

    with transaction.atomic():
        models.PasswordResetToken.objects.filter(user=user).delete()
        models.PasswordResetToken.objects.create(user=user, expires_at=(
            datetime.datetime.utcnow() + _PASSWORDRESETTOKEN_EXPIRY_INTERVAL))

    # TODO send out emails

    return HttpResponse()


def _passwordresettoken_reset_post(request):
    token = request.POST.get('token')
    if token is None:
        return HttpResponseBadRequest('\'token\' missing')

    password = request.POST.get('password')
    if password is None:
        return HttpResponseBadRequest('\'password\' missing')

    password_reset_token = models.PasswordResetToken.find_by_token(token)

    if password_reset_token is None:
        return HttpResponseNotFound('token not valid')

    my_login = models.MyLogin.objects.get(user_id=password_reset_token.user_id)

    my_login.pw_hash = password_hasher().hash(password)

    with transaction.atomic():
        my_login.save()

        password_reset_token.delete()

    return HttpResponse()
