from typing import Any, cast

from dj_rest_auth.views import LoginView as _LoginView
from dj_rest_auth.views import LogoutView as _LogoutView
from dj_rest_auth.views import PasswordChangeView as _PasswordChangeView
from dj_rest_auth.views import PasswordResetConfirmView as _PasswordResetConfirmView
from dj_rest_auth.views import PasswordResetView as _PasswordResetView
from dj_rest_auth.views import UserDetailsView as _UserDetailsView
from django.conf import settings
from django.http.response import HttpResponseBase
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


class LoginView(_LoginView):  # pragma: no cover
    @swagger_auto_schema(
        operation_summary="Login and return token",
        operation_description="Login and return token",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class LogoutView(_LogoutView):  # pragma: no cover
    @swagger_auto_schema(auto_schema=None)
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Logout and delete token",
        operation_description="Logout and delete token",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class PasswordChangeView(_PasswordChangeView):  # pragma: no cover
    @sensitive_post_parameters_m
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        return super().dispatch(*args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Change your password",
        operation_description="Change your password",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class PasswordResetView(_PasswordResetView):  # pragma: no cover
    @swagger_auto_schema(
        operation_summary="Initiate a password reset",
        operation_description="Initiate a password reset",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class PasswordResetConfirmView(_PasswordResetConfirmView):  # pragma: no cover
    @sensitive_post_parameters_m
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        return super().dispatch(*args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Complete a password reset",
        operation_description="Complete a password reset",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class UserDetailsView(_UserDetailsView):  # pragma: no cover
    @swagger_auto_schema(
        operation_summary="Return details about your user profile",
        operation_description="Return details about your user profile",
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Set details about your user profile",
        operation_description="Set details about your user profile",
    )
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Patch details about your user profile",
        operation_description="Patch details about your user profile",
    )
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().patch(request, *args, **kwargs)


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


__all__ = [
    "LoginView",
    "LogoutView",
    "PasswordChangeView",
    "PasswordResetView",
    "PasswordResetConfirmView",
    "UserDetailsView",
    "UserAttributesView",
]
