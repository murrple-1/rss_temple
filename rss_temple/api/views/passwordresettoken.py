import datetime

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseNotFound
from django.db import transaction

import ujson

from api import models
from api.password_hasher import password_hasher

_PASSWORDRESETTOKEN_EXPIRY_INTERVAL = settings.PASSWORDRESETTOKEN_EXPIRY_INTERVAL


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
    email = request.GET.get('email')

    if email is None:
        return HttpResponseBadRequest('\'email\' missing')

    user = None
    try:
        user = models.User.objects.get(email=email)
    except models.User.DoesNotExist:
        return HttpResponse()

    with transaction.atomic():
        models.PasswordResetToken.objects.filter(user=user).delete()
        models.PasswordResetToken.objects.create(user=user, expires_at=(datetime.datetime.utcnow() + _PASSWORDRESETTOKEN_EXPIRY_INTERVAL))

    # TODO send out emails

    return HttpResponse()


def _passwordresettoken_reset_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, dict):
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    if 'token' not in _json:
        return HttpResponseBadRequest('\'token\' missing')

    if not isinstance(_json['token'], str):
        return HttpResponseBadRequest('\'token\' must be string')

    if 'password' not in _json:
        return HttpResponseBadRequest('\'password\' missing')

    if not isinstance(_json['password'], str):
        return HttpResponseBadRequest('\'password\' must be string')

    password_reset_token = models.PasswordResetToken.find_by_token(_json['token'])

    if password_reset_token is None:
        return HttpResponseNotFound('token not valid')

    my_login = models.MyLogin.objects.get(user_id=password_reset_token.user_id)

    my_login.pw_hash = password_hasher().hash(_json['password'])

    with transaction.atomic():
        my_login.save()

        password_reset_token.delete()

    return HttpResponse()
