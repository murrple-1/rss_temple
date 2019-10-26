import datetime
import uuid

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed
from django.db import transaction

import argon2

import ujson

from validate_email import validate_email

import facebook

from google.oauth2 import id_token as g_id_token
from google.auth.transport import requests as g_requests

from api import models, query_utils
from api.password_hasher import password_hasher

_GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
_USER_VERIFICATION_EXPIRY_INTERVAL = settings.USER_VERIFICATION_EXPIRY_INTERVAL


def my_login(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _my_login_post(request)


def google_login(request):  # pragma: no cover
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _google_login_post(request)


def facebook_login(request):  # pragma: no cover
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


def google_login_session(request):  # pragma: no cover
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _google_login_session_post(request)


def facebook_login_session(request):  # pragma: no cover
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _facebook_login_session_post(request)


def session(request):
    permitted_methods = {'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'DELETE':
        return _session_delete(request)


def _my_login_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not dict:
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    if 'email' not in json_:
        return HttpResponseBadRequest('\'email\' missing')  # pragma: no cover

    if type(json_['email']) is not str:
        return HttpResponseBadRequest('\'email\' must be string')  # pragma: no cover

    if not validate_email(json_['email']):
        return HttpResponseBadRequest('\'email\' malformed')  # pragma: no cover

    if 'password' not in json_:
        return HttpResponseBadRequest('\'password\' missing')  # pragma: no cover

    if type(json_['password']) is not str:
        return HttpResponseBadRequest('\'password\' must be string')  # pragma: no cover

    if models.MyLogin.objects.filter(user__email=json_['email']).exists():
        return HttpResponse('login already exists', status=409)

    verification_token = None

    with transaction.atomic():
        user = None
        try:
            user = models.User.objects.get(email=json_['email'])
        except models.User.DoesNotExist:
            user = models.User.objects.create(email=json_['email'])

            verification_token = models.VerificationToken.objects.create(user=user, expires_at=(
                datetime.datetime.utcnow() + _USER_VERIFICATION_EXPIRY_INTERVAL))

        models.MyLogin.objects.create(
            pw_hash=password_hasher().hash(json_['password']),
            user=user)

    if verification_token is not None:
        # TODO new email verification
        pass

    return HttpResponse()


def _google_login_post(request):  # pragma: no cover
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not dict:
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    if 'email' not in json_:
        return HttpResponseBadRequest('\'email\' missing')  # pragma: no cover

    if type(json_['email']) is not str:
        return HttpResponseBadRequest('\'email\' must be string')  # pragma: no cover

    if not validate_email(json_['email']):
        return HttpResponseBadRequest('\'email\' malformed')  # pragma: no cover

    if 'password' not in json_:
        return HttpResponseBadRequest('\'password\' missing')  # pragma: no cover

    if type(json_['password']) is not str:
        return HttpResponseBadRequest('\'password\' must be string')  # pragma: no cover

    if 'token' not in json_:
        return HttpResponseBadRequest('\'token\' missing')  # pragma: no cover

    if type(json_['token']) is not str:
        return HttpResponseBadRequest('\'token\' must be string')  # pragma: no cover

    idinfo = None
    try:
        idinfo = g_id_token.verify_oauth2_token(
            json_['token'], g_requests.Request(), _GOOGLE_CLIENT_ID)
    except ValueError:
        return HttpResponseBadRequest('bad Google token')

    if (
        models.GoogleLogin.objects.filter(g_user_id=idinfo['sub']).exists()
        or models.MyLogin.objects.filter(user__email=json_['email']).exists()
    ):
        return HttpResponse('login already exists', status=409)

    verification_token = None

    with transaction.atomic():
        user = None
        try:
            user = models.User.objects.get(email=json_['email'])
        except models.User.DoesNotExist:
            user = models.User.objects.create(email=json_['email'])

            verification_token = models.VerificationToken.objects.create(user=user, expires_at=(
                datetime.datetime.utcnow() + _USER_VERIFICATION_EXPIRY_INTERVAL))

        models.MyLogin.objects.create(
            pw_hash=password_hasher().hash(json_['password']),
            user=user)

        models.GoogleLogin.objects.create(
            g_user_id=idinfo['sub'],
            user=user)

    if verification_token is not None:
        # TODO new email verification
        pass

    return HttpResponse()


def _facebook_login_post(request):  # pragma: no cover
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not dict:
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    if 'email' not in json_:
        return HttpResponseBadRequest('\'email\' missing')  # pragma: no cover

    if type(json_['email']) is not str:
        return HttpResponseBadRequest('\'email\' must be string')  # pragma: no cover

    if not validate_email(json_['email']):
        return HttpResponseBadRequest('\'email\' malformed')  # pragma: no cover

    if 'password' not in json_:
        return HttpResponseBadRequest('\'password\' missing')  # pragma: no cover

    if type(json_['password']) is not str:
        return HttpResponseBadRequest('\'password\' must be string')  # pragma: no cover

    if 'token' not in json_:
        return HttpResponseBadRequest('\'token\' missing')  # pragma: no cover

    if type(json_['token']) is not str:
        return HttpResponseBadRequest('\'token\' must be string')  # pragma: no cover

    graph = facebook.GraphAPI(json_['token'])

    profile = None
    try:
        profile = graph.get_object('me', fields='id')
    except facebook.GraphAPIError:
        return HttpResponseBadRequest('bad Facebook token')

    if (
        models.FacebookLogin.objects.filter(profile_id=profile['id']).exists()
        or models.MyLogin.objects.filter(user__email=json_['email']).exists()
    ):
        return HttpResponse('login already exists', status=409)

    verification_token = None

    with transaction.atomic():
        user = None
        try:
            user = models.User.objects.get(email=json_['email'])
        except models.User.DoesNotExist:
            user = models.User.objects.create(email=json_['email'])

            verification_token = models.VerificationToken.objects.create(user=user, expires_at=(
                datetime.datetime.utcnow() + _USER_VERIFICATION_EXPIRY_INTERVAL))

        models.MyLogin.objects.create(
            pw_hash=password_hasher().hash(json_['password']),
            user=user)

        models.FacebookLogin.objects.create(
            profile_id=profile['id'],
            user=user)

    if verification_token is not None:
        # TODO new email verification
        pass

    return HttpResponse()


_SESSION_EXPIRY_INTERVAL = settings.SESSION_EXPIRY_INTERVAL


def _my_login_session_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not dict:
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    if 'email' not in json_:
        return HttpResponseBadRequest('\'email\' missing')  # pragma: no cover

    if type(json_['email']) is not str:
        return HttpResponseBadRequest('\'email\' must be string')  # pragma: no cover

    if 'password' not in json_:
        return HttpResponseBadRequest('\'password\' missing')  # pragma: no cover

    if type(json_['password']) is not str:
        return HttpResponseBadRequest('\'password\' must be string')  # pragma: no cover

    my_login = None
    try:
        my_login = models.MyLogin.objects.get(user__email=json_['email'])
    except models.MyLogin.DoesNotExist:
        return HttpResponseForbidden()

    try:
        password_hasher().verify(my_login.pw_hash, json_['password'])
    except argon2.exceptions.VerifyMismatchError:
        return HttpResponseForbidden()

    session = models.Session.objects.create(
        user=my_login.user,
        expires_at=datetime.datetime.utcnow() + _SESSION_EXPIRY_INTERVAL,
    )

    content, content_type = query_utils.serialize_content(str(session.uuid))
    return HttpResponse(content, content_type)


def _google_login_session_post(request):  # pragma: no cover
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not dict:
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    if 'token' not in json_:
        return HttpResponseBadRequest('\'token\' missing')

    if type(json_['token']) is not str:
        return HttpResponseBadRequest('\'token\' must be string')

    idinfo = None
    try:
        idinfo = g_id_token.verify_oauth2_token(
            json_['token'], g_requests.Request(), _GOOGLE_CLIENT_ID)
    except ValueError:
        return HttpResponseBadRequest('bad Google token')

    google_login = None
    try:
        google_login = models.GoogleLogin.objects.get(g_user_id=idinfo['sub'])
    except models.GoogleLogin.DoesNotExist:
        ret_obj = {
            'token': json_['token'],
            'email': idinfo.get('email'),
        }

        content, content_type = query_utils.serialize_content(ret_obj)
        return HttpResponse(content, content_type, status=422)

    session = models.Session.objects.create(
        user=google_login.user,
        expires_at=datetime.datetime.utcnow() + _SESSION_EXPIRY_INTERVAL,
    )

    content, content_type = query_utils.serialize_content(str(session.uuid))
    return HttpResponse(content, content_type)


def _facebook_login_session_post(request):  # pragma: no cover
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not dict:
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    if 'token' not in json_:
        return HttpResponseBadRequest('\'token\' missing')

    if type(json_['token']) is not str:
        return HttpResponseBadRequest('\'token\' must be string')

    graph = facebook.GraphAPI(json_['token'])

    profile = None
    try:
        profile = graph.get_object('me', fields='id,email')
    except facebook.GraphAPIError:
        return HttpResponseBadRequest('bad Facebook token')

    facebook_login = None
    try:
        facebook_login = models.FacebookLogin.objects.get(
            profile_id=profile['id'])
    except models.FacebookLogin.DoesNotExist:
        ret_obj = {
            'token': json_['token'],
            'email': profile.get('email'),
        }

        content, content_type = query_utils.serialize_content(ret_obj)
        return HttpResponse(content, content_type, status=422)

    session = models.Session.objects.create(
        user=facebook_login.user,
        expires_at=datetime.datetime.utcnow() + _SESSION_EXPIRY_INTERVAL,
    )

    content, content_type = query_utils.serialize_content(str(session.uuid))
    return HttpResponse(content, content_type)


def _session_delete(request):
    session_token = request.META.get('HTTP_X_SESSION_TOKEN')
    if session_token is None:
        return HttpResponseBadRequest('\'X-Session-Token\' header missing')

    session_token_uuid = None
    try:
        session_token_uuid = uuid.UUID(session_token)
    except ValueError:
        return HttpResponseBadRequest('\'X-Session-Token\' header malformed')

    models.Session.objects.filter(uuid=session_token_uuid).delete()

    return HttpResponse()
