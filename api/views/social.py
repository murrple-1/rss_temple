from typing import Any

from allauth.socialaccount import signals
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.serializers import SocialConnectSerializer
from dj_rest_auth.registration.views import (
    SocialAccountListView as _SocialAccountListView,
)
from dj_rest_auth.registration.views import SocialConnectView, SocialLoginView
from drf_yasg.utils import swagger_auto_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from api.serializers import LoginAdditionalParamsSerializer, SocialLoginSerializer


class SocialAccountListView(_SocialAccountListView):
    @swagger_auto_schema(
        operation_summary="List which social accounts are linked with your user account",
        operation_description="List which social accounts are linked with your user account",
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)


class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    serializer_class = SocialLoginSerializer

    @swagger_auto_schema(
        operation_summary="Login or create account via Google",
        operation_description="Login or create account via Google",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().post(request, *args, **kwargs)

        serializer = LoginAdditionalParamsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stay_logged_in: bool = serializer.validated_data["stay_logged_in"]
        if not stay_logged_in:
            request.session.set_expiry(0)

        return response


class GoogleConnect(SocialConnectView):
    adapter_class = GoogleOAuth2Adapter

    @swagger_auto_schema(
        operation_summary="Connect your account to Google",
        operation_description="Connect your account to Google",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class GoogleDisconnect(GenericAPIView):
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


class FacebookLogin(SocialLoginView):
    adapter_class = FacebookOAuth2Adapter
    serializer_class = SocialLoginSerializer

    @swagger_auto_schema(
        operation_summary="Login or create account via Facebook",
        operation_description="Login or create account via Facebook",
        security=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().post(request, *args, **kwargs)

        serializer = LoginAdditionalParamsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stay_logged_in: bool = serializer.validated_data["stay_logged_in"]
        if not stay_logged_in:
            request.session.set_expiry(0)

        return response


class FacebookConnect(SocialConnectView):
    adapter_class = FacebookOAuth2Adapter

    @swagger_auto_schema(
        operation_summary="Connect your account to Facebook",
        operation_description="Connect your account to Facebook",
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


class FacebookDisconnect(GenericAPIView):
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
