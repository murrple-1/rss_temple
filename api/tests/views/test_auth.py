import datetime
import logging
from typing import ClassVar

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core import mail
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import Token, User
from api.tests.utils import debug_print_last_email, throttling_monkey_patch


class AuthTestCase(APITestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)
        logging.getLogger("django").setLevel(logging.CRITICAL)

        throttling_monkey_patch()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    def test_LoginView_post(self):
        user = User.objects.create_user("test@test.com", "password")

        EmailAddress.objects.create(
            user=user, email="test@test.com", primary=True, verified=True
        )

        response = self.client.post(
            "/api/auth/login",
            {
                "email": "test@test.com",
                "password": "password",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("key", json_)
        self.assertIsInstance(json_["key"], str)

    def test_LoginView_post_unverified(self):
        user = User.objects.create_user("test@test.com", "password")

        EmailAddress.objects.create(
            user=user, email="test@test.com", primary=True, verified=False
        )

        response = self.client.post(
            "/api/auth/login",
            {
                "email": "test@test.com",
                "password": "password",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_LoginView_post_bad_credentials(self):
        response = self.client.post(
            "/api/auth/login",
            {
                "email": "unknown@test.com",
                "password": "badpassword",
            },
        )
        self.assertEqual(response.status_code, 401, response.content)

    def test_LogoutView_post(self):
        user = User.objects.create_user("test@test.com", None)
        setattr(
            user,
            "_token",
            Token.objects.create(
                user=user, expires_at=timezone.now() + datetime.timedelta(days=14)
            ),
        )

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/auth/logout",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

    def test_LogoutView_post_no_user(self):
        response = self.client.post(
            "/api/auth/logout",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

    def test_PasswordChangeView_post(self):
        user = User.objects.create_user("test@test.com", "password")

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/auth/password/change",
            {
                "oldPassword": "password",
                "newPassword": "aC0mplic?tedTestPassword",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

        self.assertTrue(
            self.client.login(
                email="test@test.com", password="aC0mplic?tedTestPassword"
            )
        )
        self.assertFalse(self.client.login(email="test@test.com", password="password"))

    def test_PasswordChangeView_post_weak_password(self):
        user = User.objects.create_user("test@test.com", "password")

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/auth/password/change",
            {
                "oldPassword": "password",
                "newPassword": "password2",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_PasswordResetView_post(self):
        initial_outbox_count = len(getattr(mail, "outbox", []))

        User.objects.create_user("test@test.com", "password")

        response = self.client.post(
            "/api/auth/password/reset",
            {
                "email": "test@test.com",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

        self.assertGreater(len(getattr(mail, "outbox")), initial_outbox_count)
        debug_print_last_email()

    def test_PasswordResetConfirmView_post(self):
        if "allauth" in settings.INSTALLED_APPS:
            from allauth.account.forms import default_token_generator
        else:
            from django.contrib.auth.tokens import default_token_generator

        user = User.objects.create_user("test@test.com", None)

        response = self.client.post(
            "/api/auth/password/reset/confirm",
            {
                "newPassword": "aC0mplic?tedTestPassword",
                "userUuid": str(user.uuid),
                "token": default_token_generator.make_token(user),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

        self.assertTrue(
            self.client.login(
                email="test@test.com", password="aC0mplic?tedTestPassword"
            )
        )

        user = User.objects.create_user("test2@test.com", "password")

        response = self.client.post(
            "/api/auth/password/reset/confirm",
            {
                "newPassword": "aC0mplic?tedTestPassword",
                "userUuid": str(user.uuid),
                "token": default_token_generator.make_token(user),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

        self.assertTrue(
            self.client.login(
                email="test2@test.com", password="aC0mplic?tedTestPassword"
            )
        )
        self.assertFalse(self.client.login(email="test2@test.com", password="password"))

    def test_PasswordResetConfirmView_post_weak_password(self):
        if "allauth" in settings.INSTALLED_APPS:
            from allauth.account.forms import default_token_generator
        else:
            from django.contrib.auth.tokens import default_token_generator

        user = User.objects.create_user("test@test.com", None)

        response = self.client.post(
            "/api/auth/password/reset/confirm",
            {
                "newPassword": "password2",
                "userId": str(user.uuid),
                "token": default_token_generator.make_token(user),
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_UserDetailsView_get(self):
        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.get(
            "/api/auth/user",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIn("subscribedFeedUuids", json_)

    def test_UserAttributesView_put(self):
        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        body = {
            "test": "test_string",
        }
        response = self.client.put(
            "/api/auth/user/attributes",
            body,
        )
        self.assertEqual(response.status_code, 204, response.content)

        user.refresh_from_db()
        self.assertIn("test", user.attributes)
        self.assertEqual(user.attributes["test"], "test_string")

    def test_UserAttributesView_put_deletekeys(self):
        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        user.attributes["test"] = "test_string"
        user.save()

        body = {
            "test": None,
        }

        response = self.client.put(
            "/api/auth/user/attributes",
            body,
        )
        self.assertEqual(response.status_code, 204, response.content)

        user.refresh_from_db()
        self.assertNotIn("test", user.attributes)

    def test_UserDeleteView_post(self):
        user = User.objects.create_user("test@test.com", "password")

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/auth/user/delete",
            {
                "password": "password",
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_UserDeleteView_post_badpassword(self):
        user = User.objects.create_user("test@test.com", "password")

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/auth/user/delete",
            {
                "password": "badpassword",
            },
        )
        self.assertEqual(response.status_code, 401, response.content)

    def test_UserDeleteView_post_password_missing(self):
        user = User.objects.create_user("test@test.com", "password")

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/auth/user/delete",
            {},
        )
        self.assertEqual(response.status_code, 400, response.content)
