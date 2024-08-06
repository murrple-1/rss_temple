from typing import Any

from dj_rest_auth.registration.views import RegisterView as _RegisterView
from dj_rest_auth.registration.views import (
    ResendEmailVerificationView as _ResendEmailVerificationView,
)
from dj_rest_auth.registration.views import VerifyEmailView as _VerifyEmailView
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from api import throttling

sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters("password"),
)


class RegisterView(_RegisterView):
    @sensitive_post_parameters_m
    def dispatch(self, *args: Any, **kwargs: Any):
        return super().dispatch(*args, **kwargs)

    @extend_schema(
        summary="Register an account",
        description="Register an account",
        auth=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class VerifyEmailView(_VerifyEmailView):
    throttle_classes = (throttling.AnonRateThrottle,)

    @extend_schema(
        summary="Verify your account",
        description="""Verify your account

The link to access this URL most likely came through an email""",
        auth=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class ResendEmailVerificationView(_ResendEmailVerificationView):
    throttle_classes = (throttling.AnonRateThrottle,)

    @extend_schema(
        summary="Request the verification email be re-sent",
        description="Request the verification email be re-sent",
        auth=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


__all__ = [
    "RegisterView",
    "VerifyEmailView",
    "ResendEmailVerificationView",
]
