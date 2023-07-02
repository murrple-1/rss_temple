import datetime
import uuid
from typing import Any, cast

import ujson
import validators
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.signals import setting_changed
from django.db import transaction
from django.dispatch import receiver
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseBase,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
)
from django.utils import timezone
from throttle.decorators import throttle

from api import query_utils
from api.models import (
    APISession,
    FacebookLogin,
    GoogleLogin,
    NotifyEmailQueueEntry,
    NotifyEmailQueueEntryRecipient,
    User,
    VerificationToken,
)
from api.render import verify as verifyrender
from api.third_party_login import facebook, google

_USER_VERIFICATION_EXPIRY_INTERVAL: datetime.timedelta
_API_SESSION_EXPIRY_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _USER_VERIFICATION_EXPIRY_INTERVAL
    global _API_SESSION_EXPIRY_INTERVAL

    _USER_VERIFICATION_EXPIRY_INTERVAL = settings.USER_VERIFICATION_EXPIRY_INTERVAL
    _API_SESSION_EXPIRY_INTERVAL = settings.API_SESSION_EXPIRY_INTERVAL


_load_global_settings()


@throttle(zone="default")
def my_login(request: HttpRequest) -> HttpResponseBase:
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _my_login_post(request)
    else:  # pragma: no cover
        raise ValueError


@throttle(zone="default")
def google_login(request: HttpRequest) -> HttpResponseBase:  # pragma: no cover
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _google_login_post(request)
    else:  # pragma: no cover
        raise ValueError


@throttle(zone="default")
def facebook_login(request: HttpRequest) -> HttpResponseBase:  # pragma: no cover
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _facebook_login_post(request)
    else:  # pragma: no cover
        raise ValueError


@throttle(zone="default")
def my_login_session(request: HttpRequest) -> HttpResponseBase:
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _my_login_session_post(request)
    else:  # pragma: no cover
        raise ValueError


@throttle(zone="default")
def google_login_session(request: HttpRequest) -> HttpResponseBase:  # pragma: no cover
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _google_login_session_post(request)
    else:  # pragma: no cover
        raise ValueError


@throttle(zone="default")
def facebook_login_session(
    request: HttpRequest,
) -> HttpResponseBase:  # pragma: no cover
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _facebook_login_session_post(request)
    else:  # pragma: no cover
        raise ValueError


@throttle(zone="default")
def session(request: HttpRequest) -> HttpResponseBase:
    permitted_methods = {"DELETE"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "DELETE":
        return _session_delete(request)
    else:  # pragma: no cover
        raise ValueError


def _prepare_verify_notification(token_str: str, email: str):
    subject = verifyrender.subject()
    plain_text = verifyrender.plain_text(token_str)
    html_text = verifyrender.html_text(token_str)

    email_queue_entry = NotifyEmailQueueEntry.objects.create(
        subject=subject, plain_text=plain_text, html_text=html_text
    )
    NotifyEmailQueueEntryRecipient.objects.create(
        type=NotifyEmailQueueEntryRecipient.TYPE_TO,
        email=email,
        entry=email_queue_entry,
    )


def _my_login_post(request: HttpRequest):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_: Any
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    assert isinstance(json_, dict)

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

    if User.objects.filter(email__iexact=json_["email"]).exists():
        return HttpResponse("login already exists", status=409)

    with transaction.atomic():
        user = User.objects.create_user(json_["email"], json_["password"])

        verification_token = VerificationToken.objects.create(
            user=user,
            expires_at=(timezone.now() + _USER_VERIFICATION_EXPIRY_INTERVAL),
        )

        _prepare_verify_notification(verification_token.token_str(), json_["email"])

    return HttpResponse(status=204)


def _google_login_post(request: HttpRequest):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_: Any
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    assert isinstance(json_, dict)

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

    g_user_id: str
    try:
        g_user_id = google.get_id(json_["token"])
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("bad Google token")

    if (
        GoogleLogin.objects.filter(g_user_id=g_user_id).exists()
        or User.objects.filter(email__iexact=json_["email"]).exists()
    ):
        return HttpResponse("login already exists", status=409)

    verification_token: VerificationToken | None

    with transaction.atomic():
        user = User.objects.create_user(json_["email"], json_["password"])

        verification_token = VerificationToken.objects.create(
            user=user,
            expires_at=(timezone.now() + _USER_VERIFICATION_EXPIRY_INTERVAL),
        )

        GoogleLogin.objects.create(g_user_id=g_user_id, user=user)

        _prepare_verify_notification(verification_token.token_str(), json_["email"])

    return HttpResponse(status=204)


def _facebook_login_post(request: HttpRequest):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_: Any
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    assert isinstance(json_, dict)

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

    fb_id: str
    try:
        fb_id = facebook.get_id(json_["token"])
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("bad Facebook token")

    if (
        FacebookLogin.objects.filter(profile_id=fb_id).exists()
        or User.objects.filter(email__iexact=json_["email"]).exists()
    ):
        return HttpResponse("login already exists", status=409)

    with transaction.atomic():
        user = User.objects.create_user(json_["email"], json_["password"])

        verification_token = VerificationToken.objects.create(
            user=user,
            expires_at=(timezone.now() + _USER_VERIFICATION_EXPIRY_INTERVAL),
        )

        FacebookLogin.objects.create(profile_id=fb_id, user=user)

        _prepare_verify_notification(verification_token.token_str(), json_["email"])

    return HttpResponse(status=204)


def _my_login_session_post(request: HttpRequest):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_: Any
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    assert isinstance(json_, dict)

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

    session = APISession.objects.create(
        user=cast(User, user),
        expires_at=timezone.now() + _API_SESSION_EXPIRY_INTERVAL,
    )

    content, content_type = query_utils.serialize_content(session.id_str())
    return HttpResponse(content, content_type)


def _google_login_session_post(request: HttpRequest):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_: Any
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    assert isinstance(json_, dict)

    if "token" not in json_:
        return HttpResponseBadRequest("'token' missing")

    if type(json_["token"]) is not str:
        return HttpResponseBadRequest("'token' must be string")

    g_user_id: str
    g_email: str | None
    try:
        g_user_id, g_email = google.get_id_and_email(json_["token"])
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("bad Google token")

    google_login: GoogleLogin
    try:
        google_login = GoogleLogin.objects.get(g_user_id=g_user_id)
    except GoogleLogin.DoesNotExist:
        ret_obj = {
            "token": json_["token"],
            "email": g_email,
        }

        content, content_type = query_utils.serialize_content(ret_obj)
        return HttpResponse(content, content_type, status=422)

    login(request, google_login.user)

    session = APISession.objects.create(
        user=google_login.user,
        expires_at=timezone.now() + _API_SESSION_EXPIRY_INTERVAL,
    )

    content, content_type = query_utils.serialize_content(session.id_str())
    return HttpResponse(content, content_type)


def _facebook_login_session_post(request: HttpRequest):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_: Any
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    assert isinstance(json_, dict)

    if "token" not in json_:
        return HttpResponseBadRequest("'token' missing")

    if type(json_["token"]) is not str:
        return HttpResponseBadRequest("'token' must be string")

    fb_id: str
    fb_email: str | None
    try:
        fb_id, fb_email = facebook.get_id_and_email(json_["token"])
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("bad Facebook token")

    facebook_login: FacebookLogin
    try:
        facebook_login = FacebookLogin.objects.get(profile_id=fb_id)
    except FacebookLogin.DoesNotExist:
        ret_obj = {
            "token": json_["token"],
            "email": fb_email,
        }

        content, content_type = query_utils.serialize_content(ret_obj)
        return HttpResponse(content, content_type, status=422)

    login(request, facebook_login.user)

    session = APISession.objects.create(
        user=facebook_login.user,
        expires_at=timezone.now() + _API_SESSION_EXPIRY_INTERVAL,
    )

    content, content_type = query_utils.serialize_content(session.id_str())
    return HttpResponse(content, content_type)


def _session_delete(request: HttpRequest):
    logout(request)

    if session_id := request.META.get("HTTP_X_SESSION_ID"):
        session_uuid: uuid.UUID
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            return HttpResponse(status=204)

        APISession.objects.filter(uuid=session_uuid).delete()

    return HttpResponse(status=204)
