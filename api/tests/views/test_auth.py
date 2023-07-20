import logging
from typing import ClassVar

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core import mail
from rest_framework.test import APITestCase

from api.models import User
from api.tests.utils import debug_print_last_email


class AuthTestCase(APITestCase):
    old_django_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("django").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

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

    def test_LogoutView_post(self):
        user = User.objects.create_user("test@test.com", None)

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
                "old_password": "password",
                "new_password1": "aC0mplic?tedTestPassword",
                "new_password2": "aC0mplic?tedTestPassword",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

    def test_PasswordChangeView_post_weak_password(self):
        user = User.objects.create_user("test@test.com", "password")

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/auth/password/change",
            {
                "old_password": "password",
                "new_password1": "password2",
                "new_password2": "password2",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_PasswordChangeView_post_new_passwords_dont_match(self):
        user = User.objects.create_user("test@test.com", "password")

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/auth/password/change",
            {
                "old_password": "password",
                "new_password1": "aC0mplic?tedTestPassword",
                "new_password2": "aD1ff3rEntTestPassword",
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
                "new_password1": "aC0mplic?tedTestPassword",
                "new_password2": "aC0mplic?tedTestPassword",
                "uid": str(user.uuid),
                "token": default_token_generator.make_token(user),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

        user = User.objects.create_user("test2@test.com", "password")

        response = self.client.post(
            "/api/auth/password/reset/confirm",
            {
                "new_password1": "aC0mplic?tedTestPassword",
                "new_password2": "aC0mplic?tedTestPassword",
                "uid": str(user.uuid),
                "token": default_token_generator.make_token(user),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

    def test_PasswordResetConfirmView_post_weak_password(self):
        if "allauth" in settings.INSTALLED_APPS:
            from allauth.account.forms import default_token_generator
        else:
            from django.contrib.auth.tokens import default_token_generator

        user = User.objects.create_user("test@test.com", None)

        response = self.client.post(
            "/api/auth/password/reset/confirm",
            {
                "new_password1": "password2",
                "new_password2": "password2",
                "uid": str(user.uuid),
                "token": default_token_generator.make_token(user),
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_PasswordResetConfirmView_post_new_passwords_dont_match(self):
        if "allauth" in settings.INSTALLED_APPS:
            from allauth.account.forms import default_token_generator
        else:
            from django.contrib.auth.tokens import default_token_generator

        user = User.objects.create_user("test@test.com", None)

        response = self.client.post(
            "/api/auth/password/reset/confirm",
            {
                "new_password1": "aC0mplic?tedTestPassword",
                "new_password2": "aD1ff3rEntTestPassword",
                "uid": str(user.uuid),
                "token": default_token_generator.make_token(user),
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_password_reset_confirm_redirect_get(self):
        if "allauth" in settings.INSTALLED_APPS:
            from allauth.account.forms import default_token_generator
        else:
            from django.contrib.auth.tokens import default_token_generator

        user = User.objects.create_user("test@test.com", None)

        with self.settings(
            PASSWORD_RESET_CONFIRM_FORMAT="http://test.com/passwordreset?uid={uidb64}&token={token}"
        ):
            response = self.client.get(
                f"/api/auth/redirect/passwordresetconfirm/{user.uuid}/{default_token_generator.make_token(user)}",
                follow=False,
            )
            self.assertEqual(response.status_code, 302, response.content)

            self.assertIn("Location", response.headers)
            self.assertEqual(
                response.headers["Location"],
                f"http://test.com/passwordreset?uid={user.uuid}&token={default_token_generator.make_token(user)}",
            )
