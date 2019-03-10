import datetime

from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound
from django.db import transaction
from django.conf import settings

import argon2

import ujson

from validate_email import validate_email

import facebook

from google.oauth2 import id_token as g_id_token
from google.auth.transport import requests as g_requests

from api.exceptions import QueryException
from api import query_utils, models
from api.context import Context
from api.password_hasher import password_hasher


_OBJECT_NAME = 'user'

_GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
_USER_VERIFICATION_EXPIRY_INTERVAL = settings.USER_VERIFICATION_EXPIRY_INTERVAL


def user(request):
    permitted_methods = {'GET', 'PUT'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _user_get(request)
    elif request.method == 'PUT':
        return _user_put(request)


def user_verify(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _user_verify_post(request)


def _user_get(request):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    user = request.user

    field_maps = None
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    ret_obj = query_utils.generate_return_object(field_maps, user, context)

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _user_put(request):
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

    user = request.user

    has_changed = False

    verification_token = None
    if 'email' in _json:
        if not isinstance(_json['email'], str):
            return HttpResponseBadRequest('\'email\' must be string')

        if not validate_email(_json['email']):
            return HttpResponseBadRequest('\'email\' malformed')  # pragma: no cover

        if models.User.object.filter(email=_json['email']).exists():
            return HttpResponse('email already in use', 409)

        if user.email != _json['email']:
            user.email = _json['email']

            verification_token = models.VerificationToken(user=user, expires_at=(datetime.datetime.utcnow() + _USER_VERIFICATION_EXPIRY_INTERVAL))

            has_changed = True

    my_login = None
    if 'my' in _json:
        my_json = _json['my']
        if not isinstance(my_json, dict):
            return HttpResponseBadRequest('\'my\' must be object')

        my_login = models.MyLogin.objects.get(user=user)

        if 'password' in my_json:
            password_json = my_json['password']
            if not isinstance(password_json, dict):
                return HttpResponseBadRequest('\'password\' must be object')

            if 'old' not in password_json:
                return HttpResponseBadRequest('\'old\' missing')

            if not isinstance(password_json['old'], str):
                return HttpResponseBadRequest('\'old\' must be string')

            if 'new' not in password_json:
                return HttpResponseBadRequest('\'new\' missing')

            if not isinstance(password_json['new'], str):
                return HttpResponseBadRequest('\'new\' must be string')

            try:
                password_hasher().verify(
                    my_login.pw_hash, password_json['old'])
            except argon2.exceptions.VerifyMismatchError:
                return HttpResponseForbidden()

            my_login.pw_hash = password_hasher().hash(password_json['new'])

            has_changed = True

    def google_login_db_fn(): return None
    if 'google' in _json:
        google_json = _json['google']
        if google_json is None:
            def google_login_db_fn(): return _google_login_delete(user)
            has_changed = True
        elif isinstance(google_json, dict):
            google_login = None
            try:
                google_login = models.GoogleLogin.objects.get(user=user)
            except models.GoogleLogin.DoesNotExist:
                google_login = models.GoogleLogin(user=user)

            def google_login_db_fn(): return _google_login_save(google_login)

            if 'token' in google_json:
                if not isinstance(google_json['token'], str):
                    return HttpResponseBadRequest('\'token\' must be string')

                idinfo = None
                try:
                    idinfo = g_id_token.verify_oauth2_token(
                        google_json['token'], g_requests.Request(), _GOOGLE_CLIENT_ID)
                except ValueError:
                    return HttpResponseBadRequest('bad Google token')

                google_login.g_user_id = idinfo['sub']

                has_changed = True
        else:
            return HttpResponseBadRequest('\'google\' must be object or null')

    facebook_login_db_fn = None
    if 'facebook' in _json:
        facebook_json = _json['facebook']
        if facebook_json is None:
            def facebook_login_db_fn(): return _facebook_login_delete(user)
            has_changed = True
        elif isinstance(facebook_json, dict):
            facebook_login = None
            try:
                facebook_login = models.FacebookLogin.objects.get(user=user)
            except models.FacebookLogin.DoesNotExist:
                facebook_login = models.FacebookLogin(user=user)

            def facebook_login_db_fn(): return _facebook_login_save(facebook_login)

            if 'token' in facebook_json:
                if not isinstance(facebook_json['token'], str):
                    return HttpResponseBadRequest('\'token\' must be string')

                graph = facebook.GraphAPI(facebook_json['token'])

                profile = None
                try:
                    profile = graph.get_object('me', fields='id')
                except facebook.GraphAPIError:
                    return HttpResponseBadRequest('bad Facebook token')

                facebook_login.profile_id = profile['id']

                has_changed = True
        else:
            return HttpResponseBadRequest('\'facebook\' must be object or null')

    if has_changed:
        with transaction.atomic():
            user.save()

            if my_login is not None:
                my_login.save()

            if google_login_db_fn is not None:
                google_login_db_fn()

            if facebook_login_db_fn is not None:
                facebook_login_db_fn()

            if verification_token is not None:
                models.VerificationToken.objects.filter(user=user).delete()
                verification_token.save()

    if verification_token is not None:
        # TODO new email verification
        pass

    return HttpResponse()


def _google_login_save(google_login):
    google_login.save()


def _google_login_delete(user):
    models.GoogleLogin.objects.filter(user=user).delete()


def _facebook_login_save(facebook_login):
    facebook_login.save()


def _facebook_login_delete(user):
    models.FacebookLogin.objects.filter(user=user).delete()


def _user_verify_post(request):
    token = request.GET.get('token')

    if token is None:
        return HttpResponseBadRequest('\'token\' missing')

    verification_token = models.VerificationToken.find_by_token(token)

    if verification_token is None:
        return HttpResponseNotFound('token not found')

    verification_token.delete()

    return HttpResponse()
