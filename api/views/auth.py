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
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import throttling
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import logout as django_logout

from api.models import User
from api.serializers import UserDeleteSerializer

_logger = logging.getLogger("rss_temple.views.auth")

sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters(
        "password",
        "oldPassword",
        "newPassword",
    ),
)


class LoginView(_LoginView):  # pragma: no cover
    throttle_classes = (throttling.ScopedRateThrottle,)

    @extend_schema(
        summary="Login and return token",
        description="Login and return token",
        auth=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().post(request, *args, **kwargs)

        stay_logged_in: bool = self.serializer.validated_data["stay_logged_in"]
        if not stay_logged_in:
            request.session.set_expiry(0)

        user = cast(User, self.user)
        user.last_login = timezone.now()
        user.save(update_fields=("last_login",))

        return response


class LogoutView(_LogoutView):  # pragma: no cover
    throttle_classes = (throttling.ScopedRateThrottle,)

    @extend_schema(
        exclude=True,
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Logout and delete token",
        description="Logout and delete token",
        request=None,
        responses=OpenApiTypes.NONE,
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

    @extend_schema(
        summary="Change your password",
        description="Change your password",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class PasswordResetView(_PasswordResetView):  # pragma: no cover
    throttle_classes = (throttling.ScopedRateThrottle,)

    @extend_schema(
        summary="Initiate a password reset",
        description="Initiate a password reset",
        auth=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class PasswordResetConfirmView(_PasswordResetConfirmView):  # pragma: no cover
    throttle_classes = (throttling.ScopedRateThrottle,)

    @sensitive_post_parameters_m
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        return super().dispatch(*args, **kwargs)

    @extend_schema(
        summary="Complete a password reset",
        description="Complete a password reset",
        auth=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class UserDetailsView(_UserDetailsView):  # pragma: no cover
    @extend_schema(
        summary="Return details about your user profile",
        description="Return details about your user profile",
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Set details about your user profile",
        description="Set details about your user profile",
    )
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Patch details about your user profile",
        description="Patch details about your user profile",
    )
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().patch(request, *args, **kwargs)


class UserAttributesView(APIView):
    @extend_schema(
        summary="Update the user attributes additively",
        description="""Update the user attributes additively.

The request body must be a JSON object with arbitrary key-values.
If a value is `null`, it will be deleted from the attributes.
Otherwise, that value will be added to the attribute unchanged.""",
        request=OpenApiTypes.OBJECT,
        responses={204: OpenApiResponse(description="No response body")},
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

    @extend_schema(
        responses={204: OpenApiResponse(description="No response body")},
        request=UserDeleteSerializer,
        summary="Delete your user permanently",
        description="Delete your user permanently",
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

        django_logout(request)

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
