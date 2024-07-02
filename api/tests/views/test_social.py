import logging
import os
import unittest
from typing import ClassVar

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.sites.models import Site
from django.test import tag
from rest_framework.test import APITestCase

from api.models import User
from api.tests.utils import throttling_monkey_patch


def _is_google_testable():
    return frozenset(os.environ).issuperset(
        ("TEST_GOOGLE_CLIENT_ID", "TEST_GOOGLE_SECRET")
    )


def _is_facebook_testable():
    return frozenset(os.environ).issuperset(
        ("TEST_FACEBOOK_CLIENT_ID", "TEST_FACEBOOK_SECRET")
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
        Site.objects.get_current().socialapp_set.create(
            provider="google",
            name="Google",
            client_id=os.environ["TEST_GOOGLE_CLIENT_ID"],
            secret=os.environ["TEST_GOOGLE_SECRET"],
        )

    def setup_facebook(self):
        Site.objects.get_current().socialapp_set.create(
            provider="facebook",
            name="Facebook",
            client_id=os.environ["TEST_FACEBOOK_CLIENT_ID"],
            secret=os.environ["TEST_FACEBOOK_SECRET"],
        )

    def test_SocialAccountListView_get(self):
        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.get("/api/social")
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), list)
        self.assertEqual(len(json_), 0)

    @unittest.skipIf(not _is_google_testable(), "social env vars not setup for Google")
    @tag("slow")
    def test_GoogleLogin_post(self):
        self.setup_google()

        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/social/google",
            {
                "access_token": "asdf",
                "stayLoggedIn": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    @unittest.skipIf(not _is_google_testable(), "social env vars not setup for Google")
    @tag("slow")
    def test_GoogleConnect_post(self):
        self.setup_google()

        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/social/google/connect",
            {
                "access_token": "asdf",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    @unittest.skipIf(not _is_google_testable(), "social env vars not setup for Google")
    @tag("slow")
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

    @unittest.skipIf(
        not _is_facebook_testable(), "social env vars not setup for Facebook"
    )
    @tag("slow")
    def test_FacebookLogin_post(self):
        self.setup_facebook()

        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/social/facebook",
            {
                "access_token": "asdf",
                "stayLoggedIn": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    @unittest.skipIf(
        not _is_facebook_testable(), "social env vars not setup for Facebook"
    )
    @tag("slow")
    def test_FacebookConnect_post(self):
        self.setup_facebook()

        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/social/facebook/connect",
            {
                "access_token": "asdf",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    @unittest.skipIf(
        not _is_facebook_testable(), "social env vars not setup for Facebook"
    )
    @tag("slow")
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
