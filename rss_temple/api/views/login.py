import datetime

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed
from django.db import transaction

import argon2

import ujson

from api import models

__password_hasher = argon2.PasswordHasher()

def my_login(request):
    permitted_methods = ['POST']

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)

    if request.method == 'POST':
        return _my_login_post(request)


def my_login_session(request):
    permitted_methods = ['POST']

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)

    if request.method == 'POST':
        return _my_login_session_post(request)


def _my_login_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')

    _json = None
    try:
        _json = ujson.loads(request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, dict):
        return HttpResponseBadRequest('JSON body must be object')

    if 'email' not in _json:
        return HttpResponseBadRequest('\'email\' missing')

    if not isinstance(_json['email'], str):
        return HttpResponseBadRequest('\'email\' must be string')

    if 'password' not in _json:
        return HttpResponseBadRequest('\'password\' missing')

    if not isinstance(_json['password'], str):
        return HttpResponseBadRequest('\'password\' must be string')

    if models.MyLogin.objects.filter(user__email=_json['email']).exists():
        return HttpResponse('login already exists', status=409)

    with transaction.atomic():
        user = None
        try:
            user = models.User.objects.get(email=_json['email'])
        except models.User.DoesNotExist:
            user = models.User()
            user.email = _json['email']
            user.save()

        my_login = models.MyLogin()

        my_login.pw_hash = __password_hasher.hash(_json['password'])
        my_login.user = user
        my_login.save()

    return HttpResponse()

_SESSION_EXPIRY_INTERVAL = settings.SESSION_EXPIRY_INTERVAL


def _my_login_session_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')

    _json = None
    try:
        _json = ujson.loads(request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, dict):
        return HttpResponseBadRequest('JSON body must be object')

    if 'email' not in _json:
        return HttpResponseBadRequest('\'email\' missing')

    if not isinstance(_json['email'], str):
        return HttpResponseBadRequest('\'email\' must be string')

    if 'password' not in _json:
        return HttpResponseBadRequest('\'password\' missing')

    if not isinstance(_json['password'], str):
        return HttpResponseBadRequest('\'password\' must be string')

    my_login = None
    try:
        my_login = models.MyLogin.objects.get(user__email=_json['email'])
    except models.MyLogin.DoesNotExist:
        return HttpResponseForbidden()

    try:
        __password_hasher.verify(my_login.pw_hash, _json['password'])
    except argon2.exceptions.VerifyMismatchError:
        return HttpResponseForbidden()

    session = models.Session()
    session.user = my_login.user
    session.expires_at = datetime.datetime.utcnow() + _SESSION_EXPIRY_INTERVAL

    session.save()

    return HttpResponse(str(session.uuid), 'text/plain')
