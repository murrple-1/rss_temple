import logging
import uuid

import argon2
import ujson
import validators
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.signals import setting_changed
from django.db import transaction
from django.dispatch import receiver
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
)
from django.utils import timezone

from api import models, query_utils
from api.render import verify as verifyrender
from api.third_party_login import facebook, google

_logger = logging.getLogger("rss_temple")


_USER_VERIFICATION_EXPIRY_INTERVAL = None
_SESSION_EXPIRY_INTERVAL = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _USER_VERIFICATION_EXPIRY_INTERVAL
    global _SESSION_EXPIRY_INTERVAL

    _USER_VERIFICATION_EXPIRY_INTERVAL = settings.USER_VERIFICATION_EXPIRY_INTERVAL
    _SESSION_EXPIRY_INTERVAL = settings.SESSION_EXPIRY_INTERVAL


_load_global_settings()


def my_login(request):
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _my_login_post(request)


def google_login(request):  # pragma: no cover
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _google_login_post(request)


def facebook_login(request):  # pragma: no cover
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _facebook_login_post(request)


def my_login_session(request):
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _my_login_session_post(request)


def google_login_session(request):  # pragma: no cover
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _google_login_session_post(request)


def facebook_login_session(request):  # pragma: no cover
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _facebook_login_session_post(request)


def session(request):
    permitted_methods = {"DELETE"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "DELETE":
        return _session_delete(request)


def _prepare_verify_notification(token_str, email):
    subject = verifyrender.subject()
    plain_text = verifyrender.plain_text(token_str)
    html_text = verifyrender.html_text(token_str)

    email_queue_entry = models.NotifyEmailQueueEntry.objects.create(
        subject=subject, plain_text=plain_text, html_text=html_text
    )
    models.NotifyEmailQueueEntryRecipient.objects.create(
        type=models.NotifyEmailQueueEntryRecipient.TYPE_TO,
        email=email,
        entry=email_queue_entry,
    )


def _my_login_post(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    if "email" not in json_:
        return HttpResponseBadRequest("'email' missing")

    if type(json_["email"]) is not str:
        return HttpResponseBadRequest("'email' must be string")

    if not validators.email(json_["email"]):
        return HttpResponseBadRequest("'email' malformed")

    if "password" not in json_:
        return HttpResponseBadRequest("'password' missing")

    if type(json_["password"]) is not str:
        return HttpResponseBadRequest("'password' must be string")

    if models.User.objects.filter(email__iexact=json_["email"]).exists():
        return HttpResponse("login already exists", status=409)

    with transaction.atomic():
        user = None
        verification_token = None
        try:
            user = models.User.objects.get(email__iexact=json_["email"])
        except models.User.DoesNotExist:
            user = models.User.objects.create_user(json_["email"], json_["password"])

            verification_token = models.VerificationToken.objects.create(
                user=user,
                expires_at=(timezone.now() + _USER_VERIFICATION_EXPIRY_INTERVAL),
            )

        if verification_token is not None:
            _prepare_verify_notification(verification_token.token_str(), json_["email"])

    return HttpResponse(status=204)


def _google_login_post(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    if "email" not in json_:
        return HttpResponseBadRequest("'email' missing")

    if type(json_["email"]) is not str:
        return HttpResponseBadRequest("'email' must be string")

    if not validators.email(json_["email"]):
        return HttpResponseBadRequest("'email' malformed")

    if "password" not in json_:
        return HttpResponseBadRequest("'password' missing")

    if type(json_["password"]) is not str:
        return HttpResponseBadRequest("'password' must be string")

    if "token" not in json_:
        return HttpResponseBadRequest("'token' missing")

    if type(json_["token"]) is not str:
        return HttpResponseBadRequest("'token' must be string")

    g_user_id = None
    try:
        g_user_id = google.get_id(json_["token"])
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("bad Google token")

    if (
        models.GoogleLogin.objects.filter(g_user_id=g_user_id).exists()
        or models.User.objects.filter(email__iexact=json_["email"]).exists()
    ):
        return HttpResponse("login already exists", status=409)

    verification_token = None

    with transaction.atomic():
        user = None
        try:
            user = models.User.objects.get(email__iexact=json_["email"])
        except models.User.DoesNotExist:
            user = models.User.objects.create_user(json_["email"], json_["password"])

            verification_token = models.VerificationToken.objects.create(
                user=user,
                expires_at=(timezone.now() + _USER_VERIFICATION_EXPIRY_INTERVAL),
            )

        models.GoogleLogin.objects.create(g_user_id=g_user_id, user=user)

        if verification_token is not None:
            _prepare_verify_notification(verification_token.token_str(), json_["email"])

    return HttpResponse(status=204)


def _facebook_login_post(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    if "email" not in json_:
        return HttpResponseBadRequest("'email' missing")

    if type(json_["email"]) is not str:
        return HttpResponseBadRequest("'email' must be string")

    if not validators.email(json_["email"]):
        return HttpResponseBadRequest("'email' malformed")

    if "password" not in json_:
        return HttpResponseBadRequest("'password' missing")

    if type(json_["password"]) is not str:
        return HttpResponseBadRequest("'password' must be string")

    if "token" not in json_:
        return HttpResponseBadRequest("'token' missing")

    if type(json_["token"]) is not str:
        return HttpResponseBadRequest("'token' must be string")

    fb_id = None
    try:
        fb_id = facebook.get_id(json_["token"])
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("bad Facebook token")

    if (
        models.FacebookLogin.objects.filter(profile_id=fb_id).exists()
        or models.User.objects.filter(email__iexact=json_["email"]).exists()
    ):
        return HttpResponse("login already exists", status=409)

    verification_token = None

    with transaction.atomic():
        user = None
        try:
            user = models.User.objects.get(email__iexact=json_["email"])
        except models.User.DoesNotExist:
            user = models.User.objects.create_user(json_["email"], json_["password"])

            verification_token = models.VerificationToken.objects.create(
                user=user,
                expires_at=(timezone.now() + _USER_VERIFICATION_EXPIRY_INTERVAL),
            )

        models.FacebookLogin.objects.create(profile_id=fb_id, user=user)

        if verification_token is not None:
            _prepare_verify_notification(verification_token.token_str(), json_["email"])

    return HttpResponse(status=204)


def _my_login_session_post(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    if "email" not in json_:
        return HttpResponseBadRequest("'email' missing")

    if type(json_["email"]) is not str:
        return HttpResponseBadRequest("'email' must be string")

    if "password" not in json_:
        return HttpResponseBadRequest("'password' missing")

    if type(json_["password"]) is not str:
        return HttpResponseBadRequest("'password' must be string")

    user = authenticate(request, username=json_["email"], password=json_["password"])
    if user is None:
        return HttpResponseForbidden()

    login(request, user)

    return HttpResponse(status=204)


def _google_login_session_post(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    if "token" not in json_:
        return HttpResponseBadRequest("'token' missing")

    if type(json_["token"]) is not str:
        return HttpResponseBadRequest("'token' must be string")

    g_user_id = None
    g_email = None
    try:
        g_user_id, g_email = google.get_id_and_email(json_["token"])
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("bad Google token")

    google_login = None
    try:
        google_login = models.GoogleLogin.objects.get(g_user_id=g_user_id)
    except models.GoogleLogin.DoesNotExist:
        ret_obj = {
            "token": json_["token"],
            "email": g_email,
        }

        content, content_type = query_utils.serialize_content(ret_obj)
        return HttpResponse(content, content_type, status=422)

    login(request, google_login.user)

    return HttpResponse(status=204)


def _facebook_login_session_post(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    if "token" not in json_:
        return HttpResponseBadRequest("'token' missing")

    if type(json_["token"]) is not str:
        return HttpResponseBadRequest("'token' must be string")

    fb_id = None
    fb_email = None
    try:
        fb_id, fb_email = facebook.get_id_and_email(json_["token"])
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("bad Facebook token")

    facebook_login = None
    try:
        facebook_login = models.FacebookLogin.objects.get(profile_id=fb_id)
    except models.FacebookLogin.DoesNotExist:
        ret_obj = {
            "token": json_["token"],
            "email": fb_email,
        }

        content, content_type = query_utils.serialize_content(ret_obj)
        return HttpResponse(content, content_type, status=422)

    login(request, facebook_login.user)

    return HttpResponse(status=204)


def _session_delete(request):
    logout(request)

    return HttpResponse(status=204)
