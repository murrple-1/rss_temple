from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialAccountDisconnectView
from dj_rest_auth.registration.views import (
    SocialAccountListView as _SocialAccountListView,
)
from dj_rest_auth.registration.views import SocialConnectView, SocialLoginView
from django.conf import settings


class SocialAccountListView(_SocialAccountListView):
    pass


class FacebookLoginView(SocialLoginView):
    adapter_class = FacebookOAuth2Adapter


class FacebookConnectView(SocialConnectView):
    adapter_class = FacebookOAuth2Adapter


class FacebookDisconnectView(SocialAccountDisconnectView):
    adapter_class = FacebookOAuth2Adapter


class GoogleLoginView(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = settings.GOOGLE_CALLBACK_URL
    client_class = OAuth2Client


class GoogleConnectView(SocialConnectView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = settings.GOOGLE_CALLBACK_URL
    client_class = OAuth2Client


class GoogleDisconnectView(SocialAccountDisconnectView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = settings.GOOGLE_CALLBACK_URL
    client_class = OAuth2Client
