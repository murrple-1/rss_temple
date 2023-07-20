from typing import Any

from dj_rest_auth.registration.views import (
    RegisterView,
    ResendEmailVerificationView,
    VerifyEmailView,
)
from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.http.response import HttpResponseBase, HttpResponseRedirect
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request

_VERIFY_URL_FORMAT: str
_VERIFICATION_EMAIL_SENT_URL_FORMAT: str


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _VERIFY_URL_FORMAT
    global _VERIFICATION_EMAIL_SENT_URL_FORMAT

    _VERIFY_URL_FORMAT = settings.VERIFY_URL_FORMAT
    _VERIFICATION_EMAIL_SENT_URL_FORMAT = settings.VERIFICATION_EMAIL_SENT_URL_FORMAT


_load_global_settings()


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def verify_email_redirect(request: Request, key: str) -> HttpResponseBase:
    if request.method == "GET":
        return _verify_email_redirect_get(request, key)
    else:  # pragma: no cover
        raise ValueError


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def email_verification_sent_redirect(request: Request) -> HttpResponseBase:
    if request.method == "GET":
        return _email_verification_sent_redirect_get(request)
    else:  # pragma: no cover
        raise ValueError


def _verify_email_redirect_get(request: Request, key: str):
    return HttpResponseRedirect(redirect_to=_VERIFY_URL_FORMAT.format(key=key))


def _email_verification_sent_redirect_get(request: Request):
    return HttpResponseRedirect(redirect_to=_VERIFICATION_EMAIL_SENT_URL_FORMAT)


__all__ = [
    "RegisterView",
    "VerifyEmailView",
    "ResendEmailVerificationView",
    "verify_email_redirect",
    "email_verification_sent_redirect",
]
