import logging
import traceback
from typing import Any, cast

from allauth.socialaccount import signals
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from dj_rest_auth.registration.serializers import SocialConnectSerializer
from dj_rest_auth.registration.views import (
    SocialAccountListView as _SocialAccountListView,
)
from dj_rest_auth.registration.views import SocialConnectView, SocialLoginView
from dj_rest_auth.views import APIView
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import User
from api.serializers import SocialLoginSerializer

_logger = logging.getLogger("rss_temple")


class _SocialHandleExceptionMixin(APIView):
    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, OAuth2Error):
            _logger.error("OAuth2 error", exc_info=exc)
            # based on default DRF error
            return Response({"detail": f"OAuth2 error: {exc}"}, status=401)

        return super().handle_exception(exc)


class SocialAccountListView(_SocialAccountListView):
    @swagger_auto_schema(
        operation_summary="List which social accounts are linked with your user account",
        operation_description="List which social accounts are linked with your user account",
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)


class GoogleLogin(SocialLoginView, _SocialHandleExceptionMixin):
    adapter_class = GoogleOAuth2Adapter
    serializer_class = SocialLoginSerializer

    @swagger_auto_schema(
        operation_summary="Login or create account via Google",
        operation_description="Login or create account via Google",
        security=[],
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


class GoogleConnect(SocialConnectView, _SocialHandleExceptionMixin):
    adapter_class = GoogleOAuth2Adapter

    @swagger_auto_schema(
        operation_summary="Connect your account to Google",
        operation_description="Connect your account to Google",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class GoogleDisconnect(GenericAPIView, _SocialHandleExceptionMixin):
    serializer_class = SocialConnectSerializer

    def get_queryset(self):
        return SocialAccount.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Disconnect your account from Google",
        operation_description="Disconnect your account from Google",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        accounts = self.get_queryset()
        account: SocialAccount
        try:
            account = accounts.get(provider="google")
        except SocialAccount.DoesNotExist:
            raise NotFound

        get_social_adapter(self.request).validate_disconnect(account, accounts)

        account.delete()
        signals.social_account_removed.send(
            sender=SocialAccount,
            request=self.request,
            socialaccount=account,
        )

        return Response(self.get_serializer(account).data)


class FacebookLogin(SocialLoginView, _SocialHandleExceptionMixin):
    adapter_class = FacebookOAuth2Adapter
    serializer_class = SocialLoginSerializer

    @swagger_auto_schema(
        operation_summary="Login or create account via Facebook",
        operation_description="Login or create account via Facebook",
        security=[],
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

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, OAuth2Error):
            return Response({"test": "TEST"}, 401)

        return super().handle_exception(exc)


class FacebookConnect(SocialConnectView, _SocialHandleExceptionMixin):
    adapter_class = FacebookOAuth2Adapter

    @swagger_auto_schema(
        operation_summary="Connect your account to Facebook",
        operation_description="Connect your account to Facebook",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class FacebookDisconnect(GenericAPIView, _SocialHandleExceptionMixin):
    serializer_class = SocialConnectSerializer

    def get_queryset(self):
        return SocialAccount.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Disconnect your account from Facebook",
        operation_description="Disconnect your account from Facebook",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        accounts = self.get_queryset()
        account: SocialAccount
        try:
            account = accounts.get(provider="facebook")
        except SocialAccount.DoesNotExist:
            raise NotFound

        get_social_adapter(self.request).validate_disconnect(account, accounts)

        account.delete()
        signals.social_account_removed.send(
            sender=SocialAccount,
            request=self.request,
            socialaccount=account,
        )

        return Response(self.get_serializer(account).data)


__all__ = [
    "SocialAccountListView",
    "GoogleLogin",
    "GoogleConnect",
    "GoogleDisconnect",
    "FacebookLogin",
    "FacebookConnect",
    "FacebookDisconnect",
]
