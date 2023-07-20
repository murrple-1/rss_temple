from typing import Any

from dj_rest_auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.http.response import HttpResponseBase, HttpResponseRedirect
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request

_PASSWORD_RESET_CONFIRM_FORMAT: str


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _PASSWORD_RESET_CONFIRM_FORMAT

    _PASSWORD_RESET_CONFIRM_FORMAT = settings.PASSWORD_RESET_CONFIRM_FORMAT


_load_global_settings()


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def password_reset_confirm_redirect(
    request: Request, uidb64: str, token: str
) -> HttpResponseBase:
    if request.method == "GET":
        return _password_reset_confirm_redirect_get(request, uidb64, token)
    else:  # pragma: no cover
        raise ValueError


def _password_reset_confirm_redirect_get(request: Request, uidb64: str, token: str):
    return HttpResponseRedirect(
        redirect_to=_PASSWORD_RESET_CONFIRM_FORMAT.format(uidb64=uidb64, token=token)
    )


__all__ = [
    "LoginView",
    "LogoutView",
    "PasswordChangeView",
    "PasswordResetConfirmView",
    "PasswordResetView",
]
