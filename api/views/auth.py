from typing import Any, cast

from dj_rest_auth.views import LoginView, LogoutView
from dj_rest_auth.views import PasswordChangeView as _PasswordChangeView
from dj_rest_auth.views import PasswordResetConfirmView as _PasswordResetConfirmView
from dj_rest_auth.views import PasswordResetView, UserDetailsView
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import RedirectView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import User

sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters(
        "password",
        "oldPassword",
        "newPassword",
    ),
)


class PasswordChangeView(_PasswordChangeView):
    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class PasswordResetConfirmView(_PasswordResetConfirmView):
    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class UserAttributesView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        responses={204: ""},
        request_body=openapi.Schema(
            title="User attributes",
            description="Arbitrary user attributes",
            type="object",
        ),
        operation_summary="Update the user attributes additively",
        operation_description="""Update the user attributes additively.

The request body must be a JSON object with arbitrary key-values.
If a value is `null`, it will be deleted from the attributes.
Otherwise, that value will be added to the attribute unchanged.""",
    )
    def put(self, request: Request):
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


class PasswordResetConfirmRedirectView(RedirectView):
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
    "UserAttributesView",
    "PasswordResetConfirmRedirectView",
]
