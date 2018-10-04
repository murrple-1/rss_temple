import datetime

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed
from django.db import transaction

import argon2

import ujson

import facebook

from api import models, searchqueries

_password_hasher = argon2.PasswordHasher()


def my_login(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _my_login_post(request)


def google_login(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _google_login_post(request)


def facebook_login(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _facebook_login_post(request)


def my_login_session(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _my_login_session_post(request)


def google_login_session(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _google_login_session_post(request)


def facebook_login_session(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _facebook_login_session_post(request)


def _my_login_post(request):
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

    if 'email' not in _json:
        return HttpResponseBadRequest('\'email\' missing')  # pragma: no cover

    if not isinstance(_json['email'], str):
        return HttpResponseBadRequest('\'email\' must be string')  # pragma: no cover

    if 'password' not in _json:
        return HttpResponseBadRequest('\'password\' missing')  # pragma: no cover

    if not isinstance(_json['password'], str):
        return HttpResponseBadRequest('\'password\' must be string')  # pragma: no cover

    if models.MyLogin.objects.filter(user__email=_json['email']).exists():
        return HttpResponse('login already exists', status=409)

    with transaction.atomic():
        user = None
        try:
            user = models.User.objects.get(email=_json['email'])
        except models.User.DoesNotExist:
            user = models.User(email=_json['email'])
            user.save()

        my_login = models.MyLogin(
            pw_hash=_password_hasher.hash(_json['password']),
            user=user)
        my_login.save()

    return HttpResponse()


def _facebook_login_post(request):
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

    if 'email' not in _json:
        return HttpResponseBadRequest('\'email\' missing')  # pragma: no cover

    if not isinstance(_json['email'], str):
        return HttpResponseBadRequest('\'email\' must be string')  # pragma: no cover

    if 'password' not in _json:
        return HttpResponseBadRequest('\'password\' missing')  # pragma: no cover

    if not isinstance(_json['password'], str):
        return HttpResponseBadRequest('\'password\' must be string')  # pragma: no cover

    if 'profile_id' not in _json:
        return HttpResponseBadRequest('\'profile_id\' missing')  # pragma: no cover

    if not isinstance(_json['profile_id'], str):
        return HttpResponseBadRequest('\'profile_id\' must be string')  # pragma: no cover

    if (
        models.FacebookLogin.objects.filter(profile_id=_json['profile_id']).exists()
        or models.MyLogin.objects.filter(user__email=_json['email']).exists()
        ):
        return HttpResponse('login already exists', status=409)

    with transaction.atomic():
        user = None
        try:
            user = models.User.objects.get(email=_json['email'])
        except models.User.DoesNotExist:
            user = models.User(email=_json['email'])
            user.save()

        my_login = models.MyLogin(
            pw_hash=_password_hasher.hash(_json['password']),
            user=user)
        my_login.save()

        facebook_login = models.FacebookLogin(
            profile_id=_json['profile_id'],
            user=user)
        facebook_login.save()

    return HttpResponse()


_SESSION_EXPIRY_INTERVAL = settings.SESSION_EXPIRY_INTERVAL


def _my_login_session_post(request):
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

    if 'email' not in _json:
        return HttpResponseBadRequest('\'email\' missing')  # pragma: no cover

    if not isinstance(_json['email'], str):
        return HttpResponseBadRequest('\'email\' must be string')  # pragma: no cover

    if 'password' not in _json:
        return HttpResponseBadRequest('\'password\' missing')  # pragma: no cover

    if not isinstance(_json['password'], str):
        return HttpResponseBadRequest('\'password\' must be string')  # pragma: no cover

    my_login = None
    try:
        my_login = models.MyLogin.objects.get(user__email=_json['email'])
    except models.MyLogin.DoesNotExist:
        return HttpResponseForbidden()

    try:
        _password_hasher.verify(my_login.pw_hash, _json['password'])
    except argon2.exceptions.VerifyMismatchError:
        return HttpResponseForbidden()

    session = models.Session(
        user=my_login.user,
        expires_at=datetime.datetime.utcnow() + _SESSION_EXPIRY_INTERVAL,
    )
    session.save()

    return HttpResponse(str(session.uuid), 'text/plain')


def _facebook_login_session_post(request):
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

    graph = facebook.GraphAPI(_json['token'])

    profile = graph.get_object('me', fields='id,email')

    fb_login = None
    try:
        fb_login = models.FacebookLogin.objects.get(profile_id=profile['id'])
    except models.FacebookLogin.DoesNotExist:
        return HttpResponse(status=422)

    session = models.Session(
        user=fb_login.user,
        expires_at=datetime.datetime.utcnow() + _SESSION_EXPIRY_INTERVAL,
    )
    session.save()

    return HttpResponse(str(session.uuid), 'text/plain')
