import logging
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
from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from api.models import User
from api.serializers import SocialLoginSerializer

_TEST_SOCIAL_LOGIN_SERIALIZER_CLASS: type[serializers.BaseSerializer] | None
_TEST_SOCIAL_CONNECT_SERIALIZER_CLASS: type[serializers.BaseSerializer] | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _TEST_SOCIAL_LOGIN_SERIALIZER_CLASS
    global _TEST_SOCIAL_CONNECT_SERIALIZER_CLASS

    _TEST_SOCIAL_LOGIN_SERIALIZER_CLASS = getattr(
        settings, "TEST_SOCIAL_LOGIN_SERIALIZER_CLASS", None
    )
    _TEST_SOCIAL_CONNECT_SERIALIZER_CLASS = getattr(
        settings, "TEST_SOCIAL_CONNECT_SERIALIZER_CLASS", None
    )


_load_global_settings()

_logger = logging.getLogger("rss_temple")


class _SocialHandleExceptionMixin(APIView):  # pragma: no cover
    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, OAuth2Error):
            _logger.error("OAuth2 error", exc_info=exc)
            # based on default DRF error
            return Response({"detail": f"OAuth2 error: {exc}"}, status=401)

        return super().handle_exception(exc)


class SocialAccountListView(_SocialAccountListView):
    @extend_schema(
        summary="List which social accounts are linked with your user account",
        description="List which social accounts are linked with your user account",
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)


class GoogleLogin(SocialLoginView, _SocialHandleExceptionMixin):
    adapter_class = GoogleOAuth2Adapter
    serializer_class = SocialLoginSerializer

    def get_serializer_class(self) -> type[BaseSerializer]:
        if _TEST_SOCIAL_LOGIN_SERIALIZER_CLASS:
            return _TEST_SOCIAL_LOGIN_SERIALIZER_CLASS
        else:  # pragma: no cover
            return super().get_serializer_class()

    @extend_schema(
        summary="Login or create account via Google",
        description="Login or create account via Google",
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


class GoogleConnect(SocialConnectView, _SocialHandleExceptionMixin):
    adapter_class = GoogleOAuth2Adapter

    def get_serializer_class(self) -> type[BaseSerializer]:
        if _TEST_SOCIAL_CONNECT_SERIALIZER_CLASS:
            return _TEST_SOCIAL_CONNECT_SERIALIZER_CLASS
        else:  # pragma: no cover
            return super().get_serializer_class()

    @extend_schema(
        summary="Connect your account to Google",
        description="Connect your account to Google",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class GoogleDisconnect(GenericAPIView, _SocialHandleExceptionMixin):
    serializer_class = SocialConnectSerializer

    def get_queryset(self):
        return SocialAccount.objects.filter(user=self.request.user)

    @extend_schema(
        summary="Disconnect your account from Google",
        description="Disconnect your account from Google",
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

    def get_serializer_class(self) -> type[BaseSerializer]:
        if _TEST_SOCIAL_LOGIN_SERIALIZER_CLASS:
            return _TEST_SOCIAL_LOGIN_SERIALIZER_CLASS
        else:  # pragma: no cover
            return super().get_serializer_class()

    @extend_schema(
        summary="Login or create account via Facebook",
        description="Login or create account via Facebook",
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


class FacebookConnect(SocialConnectView, _SocialHandleExceptionMixin):
    adapter_class = FacebookOAuth2Adapter

    def get_serializer_class(self) -> type[BaseSerializer]:
        if _TEST_SOCIAL_CONNECT_SERIALIZER_CLASS:
            return _TEST_SOCIAL_CONNECT_SERIALIZER_CLASS
        else:  # pragma: no cover
            return super().get_serializer_class()

    @extend_schema(
        summary="Connect your account to Facebook",
        description="Connect your account to Facebook",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class FacebookDisconnect(GenericAPIView, _SocialHandleExceptionMixin):
    serializer_class = SocialConnectSerializer

    def get_queryset(self):
        return SocialAccount.objects.filter(user=self.request.user)

    @extend_schema(
        summary="Disconnect your account from Facebook",
        description="Disconnect your account from Facebook",
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
