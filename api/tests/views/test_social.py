import logging
from typing import ClassVar

import jwt
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from dj_rest_auth.registration.serializers import SocialConnectSerializer
from django.contrib.sites.models import Site
from django.test import override_settings
from rest_framework import serializers
from rest_framework.test import APITestCase

from api.models import User
from api.serializers import SocialLoginSerializer
from api.tests.utils import throttling_monkey_patch


class _TestSocialLoginSerializer(SocialLoginSerializer):
    def validate(self, attrs):
        attrs = serializers.Serializer.validate(self, attrs)
        request = self._get_request()
        attrs["user"] = request.user
        return attrs


class _TestSocialConnectSerializer(SocialConnectSerializer):
    def validate(self, attrs):
        attrs = serializers.Serializer.validate(self, attrs)
        request = self._get_request()
        attrs["user"] = request.user
        return attrs


@override_settings(
    TEST_SOCIAL_LOGIN_SERIALIZER_CLASS=_TestSocialLoginSerializer,
    TEST_SOCIAL_CONNECT_SERIALIZER_CLASS=_TestSocialConnectSerializer,
)
class SocialTestCase(APITestCase):
    old_django_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("django").setLevel(logging.CRITICAL)

        throttling_monkey_patch()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    def setup_google(self):
        return Site.objects.get_current().socialapp_set.create(
            provider="google",
            name="Google",
            client_id="asdf",
            secret="asdf",
        )

    def setup_facebook(self):
        return Site.objects.get_current().socialapp_set.create(
            provider="facebook",
            name="Facebook",
            client_id="asdf",
            secret="asdf",
        )

    def test_SocialAccountListView_get(self):
        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.get("/api/social")
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), list)
        self.assertEqual(len(json_), 0)

    def test_GoogleLogin_post(self):
        self.setup_google()

        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/social/google",
            {
                "access_token": jwt.encode({}, "secret", algorithm="HS256"),
                "stayLoggedIn": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_GoogleConnect_post(self):
        provider = self.setup_google()

        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/social/google/connect",
            {
                "access_token": jwt.encode({}, "secret", algorithm="HS256"),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_GoogleDisconnect_post(self):
        self.setup_google()

        user = User.objects.create_user("test@test.com", "password")
        SocialAccount.objects.create(user=user, provider="google")
        EmailAddress.objects.create(
            user=user, email="test@test.com", verified=True, primary=True
        )

        self.client.force_authenticate(user=user)

        response = self.client.post("/api/social/google/disconnect")
        self.assertEqual(response.status_code, 200, response.content)

    def test_FacebookLogin_post(self):
        self.setup_facebook()

        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/social/facebook",
            {
                "access_token": jwt.encode({}, "secret", algorithm="HS256"),
                "stayLoggedIn": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_FacebookConnect_post(self):
        self.setup_facebook()

        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/social/facebook/connect",
            {
                "access_token": jwt.encode({}, "secret", algorithm="HS256"),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_FacebookDisconnect_post(self):
        self.setup_facebook()

        user = User.objects.create_user("test@test.com", "password")
        SocialAccount.objects.create(user=user, provider="facebook")
        EmailAddress.objects.create(
            user=user, email="test@test.com", verified=True, primary=True
        )

        self.client.force_authenticate(user=user)

        response = self.client.post("/api/social/facebook/disconnect")
        self.assertEqual(response.status_code, 200, response.content)
