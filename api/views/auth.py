from typing import Any, cast

from dj_rest_auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
    UserDetailsView,
)
from django.conf import settings
from django.views.generic import RedirectView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import User


@api_view(["PUT"])
@permission_classes([permissions.IsAuthenticated])
def user_attributes(request: Request) -> Response:
    if request.method == "PUT":
        return _user_attributes_put(request)
    else:  # pragma: no cover
        raise ValueError


def _user_attributes_put(request: Request):
    if type(request.data) is not dict:
        raise ValidationError({".": "must be object"})  # pragma: no cover

    assert isinstance(request.data, dict)

    user = cast(User, request.user)

    user.attributes.update(request.data)

    del_keys = set()
    for key, value in user.attributes.items():
        if value is None:
            del_keys.add(key)

    for key in del_keys:
        del user.attributes[key]

    user.save(update_fields=["attributes"])

    return Response(status=204)


class PasswordResetConfirmRedirect(RedirectView):
    def get_redirect_url(self, *args: Any, **kwargs: Any) -> str | None:
        return settings.PASSWORD_RESET_CONFIRM_URL_FORMAT.format(
            userId=kwargs["userId"], token=kwargs["token"]
        )


__all__ = [
    "LoginView",
    "LogoutView",
    "PasswordChangeView",
    "PasswordResetView",
    "PasswordResetConfirmView",
    "UserDetailsView",
    "user_attributes",
    "PasswordResetConfirmRedirect",
]
