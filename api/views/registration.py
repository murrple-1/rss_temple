from typing import Any

from dj_rest_auth.registration.views import RegisterView as _RegisterView
from dj_rest_auth.registration.views import (
    ResendEmailVerificationView as _ResendEmailVerificationView,
)
from dj_rest_auth.registration.views import VerifyEmailView as _VerifyEmailView
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from drf_yasg.utils import swagger_auto_schema
from rest_framework.request import Request
from rest_framework.response import Response

from api import throttling

sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters("password"),
)


class RegisterView(_RegisterView):
    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Register an account",
        operation_description="Register an account",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class VerifyEmailView(_VerifyEmailView):
    throttle_classes = (throttling.AnonRateThrottle,)

    @swagger_auto_schema(
        operation_summary="Verify your account",
        operation_description="""Verify your account

The link to access this URL most likely came through an email""",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class ResendEmailVerificationView(_ResendEmailVerificationView):
    throttle_classes = (throttling.AnonRateThrottle,)

    @swagger_auto_schema(
        operation_summary="Request the verification email be re-sent",
        operation_description="Request the verification email be re-sent",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


__all__ = [
    "RegisterView",
    "VerifyEmailView",
    "ResendEmailVerificationView",
]
