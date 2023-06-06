import datetime
import logging

import argon2
import ujson
import validators
from django.conf import settings
from django.core.signals import setting_changed
from django.db import transaction
from django.dispatch import receiver
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)

from api import models, query_utils
from api.exceptions import QueryException
from api.password_hasher import password_hasher
from api.render import verify as verifyrender
from api.third_party_login import facebook, google

_logger = logging.getLogger("rss_temple")


_OBJECT_NAME = "user"


_USER_VERIFICATION_EXPIRY_INTERVAL = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _USER_VERIFICATION_EXPIRY_INTERVAL

    _USER_VERIFICATION_EXPIRY_INTERVAL = settings.USER_VERIFICATION_EXPIRY_INTERVAL


_load_global_settings()


def user(request):
    permitted_methods = {"GET", "PUT"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "GET":
        return _user_get(request)
    elif request.method == "PUT":
        return _user_put(request)


def user_verify(request):
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _user_verify_post(request)


def user_attributes(request):
    permitted_methods = {"PUT"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "PUT":
        return _user_attributes_put(request)


def _user_get(request):
    user = request.user

    field_maps = None
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    ret_obj = query_utils.generate_return_object(field_maps, user, request)

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _user_put(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    user = request.user

    has_changed = False

    verification_token = None
    if "email" in json_:
        if type(json_["email"]) is not str:
            return HttpResponseBadRequest("'email' must be string")

        if not validators.email(json_["email"]):
            return HttpResponseBadRequest("'email' malformed")  # pragma: no cover

        if user.email != json_["email"]:
            if models.User.objects.filter(email=json_["email"]).exists():
                return HttpResponse("email already in use", status=409)

            user.email = json_["email"]

            verification_token = models.VerificationToken(
                user=user,
                expires_at=(
                    datetime.datetime.now(datetime.timezone.utc)
                    + _USER_VERIFICATION_EXPIRY_INTERVAL
                ),
            )

            has_changed = True

    my_login = None
    if "my" in json_:
        my_json = json_["my"]
        if type(my_json) is not dict:
            return HttpResponseBadRequest("'my' must be object")

        my_login = user.my_login()

        if "password" in my_json:
            password_json = my_json["password"]
            if type(password_json) is not dict:
                return HttpResponseBadRequest("'password' must be object")

            if "old" not in password_json:
                return HttpResponseBadRequest("'old' missing")

            if type(password_json["old"]) is not str:
                return HttpResponseBadRequest("'old' must be string")

            if "new" not in password_json:
                return HttpResponseBadRequest("'new' missing")

            if type(password_json["new"]) is not str:
                return HttpResponseBadRequest("'new' must be string")

            try:
                password_hasher().verify(my_login.pw_hash, password_json["old"])
            except argon2.exceptions.VerifyMismatchError:
                return HttpResponseForbidden()

            my_login.pw_hash = password_hasher().hash(password_json["new"])

            has_changed = True

    google_login_db_fn = None
    if "google" in json_:
        google_json = json_["google"]
        if google_json is None:

            def google_login_db_fn():
                return _google_login_delete(user)

            has_changed = True
        elif type(google_json) is dict:
            google_login = None
            try:
                google_login = models.GoogleLogin.objects.get(user=user)
            except models.GoogleLogin.DoesNotExist:
                google_login = models.GoogleLogin(user=user)

            def google_login_db_fn():
                return _google_login_save(google_login)

            if "token" in google_json:
                if type(google_json["token"]) is not str:
                    return HttpResponseBadRequest("'token' must be string")

                try:
                    google_login.g_user_id = google.get_id(google_json["token"])
                except ValueError:  # pragma: no cover
                    return HttpResponseBadRequest("bad Google token")

                has_changed = True
        else:
            return HttpResponseBadRequest("'google' must be object or null")

    facebook_login_db_fn = None
    if "facebook" in json_:
        facebook_json = json_["facebook"]
        if facebook_json is None:

            def facebook_login_db_fn():
                return _facebook_login_delete(user)

            has_changed = True
        elif type(facebook_json) is dict:
            facebook_login = None
            try:
                facebook_login = models.FacebookLogin.objects.get(user=user)
            except models.FacebookLogin.DoesNotExist:
                facebook_login = models.FacebookLogin(user=user)

            def facebook_login_db_fn():
                return _facebook_login_save(facebook_login)

            if "token" in facebook_json:
                if type(facebook_json["token"]) is not str:
                    return HttpResponseBadRequest("'token' must be string")

                try:
                    facebook_login.profile_id = facebook.get_id(facebook_json["token"])
                except ValueError:  # pragma: no cover
                    return HttpResponseBadRequest("bad Facebook token")

                has_changed = True
        else:
            return HttpResponseBadRequest("'facebook' must be object or null")

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

                token_str = verification_token.token_str()

                subject = verifyrender.subject()
                plain_text = verifyrender.plain_text(token_str)
                html_text = verifyrender.html_text(token_str)

                email_queue_entry = models.NotifyEmailQueueEntry.objects.create(
                    subject=subject, plain_text=plain_text, html_text=html_text
                )
                models.NotifyEmailQueueEntryRecipient.objects.create(
                    type=models.NotifyEmailQueueEntryRecipient.TYPE_TO,
                    email=json_["email"],
                    entry=email_queue_entry,
                )

    return HttpResponse(status=204)


def _google_login_save(google_login):
    google_login.save()


def _google_login_delete(user):
    models.GoogleLogin.objects.filter(user=user).delete()


def _facebook_login_save(facebook_login):
    facebook_login.save()


def _facebook_login_delete(user):
    models.FacebookLogin.objects.filter(user=user).delete()


def _user_verify_post(request):
    token = request.POST.get("token")

    if token is None:
        return HttpResponseBadRequest("'token' missing")

    verification_token = models.VerificationToken.find_by_token(token)

    if verification_token is None:
        return HttpResponseNotFound("token not found")

    verification_token.delete()

    return HttpResponse(status=204)


def _user_attributes_put(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    user = request.user

    user.attributes.update(json_)

    del_keys = set()
    for key, value in user.attributes.items():
        if value is None:
            del_keys.add(key)

    for key in del_keys:
        del user.attributes[key]

    user.save(update_fields=["attributes"])

    return HttpResponse(status=204)
