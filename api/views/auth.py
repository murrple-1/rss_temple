import logging
from typing import Any, cast

from dj_rest_auth.views import LoginView as _LoginView
from dj_rest_auth.views import LogoutView as _LogoutView
from dj_rest_auth.views import PasswordChangeView as _PasswordChangeView
from dj_rest_auth.views import PasswordResetConfirmView as _PasswordResetConfirmView
from dj_rest_auth.views import PasswordResetView as _PasswordResetView
from dj_rest_auth.views import UserDetailsView as _UserDetailsView
from django.contrib.auth import authenticate
from django.http.response import HttpResponseBase
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import throttling
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import User
from api.serializers import UserDeleteSerializer

_logger = logging.getLogger("rss_temple")

sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters(
        "password",
        "oldPassword",
        "newPassword",
    ),
)


class LoginView(_LoginView):  # pragma: no cover
    throttle_classes = (throttling.ScopedRateThrottle,)

    @swagger_auto_schema(
        operation_summary="Login and return token",
        operation_description="Login and return token",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().post(request, *args, **kwargs)

        stay_logged_in: bool = self.serializer.validated_data["stay_logged_in"]
        if not stay_logged_in:
            request.session.set_expiry(0)

        return response


class LogoutView(_LogoutView):  # pragma: no cover
    throttle_classes = (throttling.ScopedRateThrottle,)

    @swagger_auto_schema(auto_schema=None)
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Logout and delete token",
        operation_description="Logout and delete token",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)

    def logout(self, request: Request):
        if (token := getattr(request.user, "_token", None)) is not None:
            token.delete()
            delattr(request.user, "_token")

        return super().logout(request)


class PasswordChangeView(_PasswordChangeView):  # pragma: no cover
    throttle_classes = (throttling.ScopedRateThrottle,)

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
    throttle_classes = (throttling.ScopedRateThrottle,)

    @swagger_auto_schema(
        operation_summary="Initiate a password reset",
        operation_description="Initiate a password reset",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class PasswordResetConfirmView(_PasswordResetConfirmView):  # pragma: no cover
    throttle_classes = (throttling.ScopedRateThrottle,)

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


class UserDeleteView(APIView):
    throttle_classes = (throttling.ScopedRateThrottle,)
    throttle_scope = "user_delete"

    @sensitive_post_parameters_m
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        return super().dispatch(*args, **kwargs)

    @swagger_auto_schema(
        responses={204: ""},
        request_body=UserDeleteSerializer,
        operation_summary="Delete your user permanently",
        operation_description="Delete your user permanently",
    )
    def post(self, request: Request):
        user = cast(User, request.user)

        serializer = UserDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_ = authenticate(
            email=user.email, password=serializer.validated_data["password"]
        )
        if not user_:
            raise AuthenticationFailed

        _logger.warn(f"DELETE USER: {user.uuid} ({user.email})")
        user.delete()

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
