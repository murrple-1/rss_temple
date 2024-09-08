import datetime
import logging
from typing import ClassVar

from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from django.core import mail
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import Captcha, User
from api.tests.utils import (
    debug_print_last_email,
    disable_silk,
    reusable_captcha_key,
    reusable_captcha_seed,
    throttling_monkey_patch,
)


@disable_silk()
class RegistrationTestCase(APITestCase):
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

    def test_RegisterView_post(self):
        initial_outbox_count = len(getattr(mail, "outbox", []))

        captcha = Captcha.objects.create(
            key=reusable_captcha_key(),
            seed=reusable_captcha_seed(),
            expires_at=(timezone.now() + datetime.timedelta(days=1)),
        )

        response = self.client.post(
            "/api/registration",
            {
                "email": "test@test.com",
                "password": "aC0mplic?tedTestPassword",
                "captcha": f"{captcha.key}:{captcha.secret_phrase}",
            },
        )
        self.assertEqual(response.status_code, 201, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

        self.assertGreater(len(getattr(mail, "outbox")), initial_outbox_count)
        debug_print_last_email()

    def test_RegisterView_post_weak_password(self):
        captcha = Captcha.objects.create(
            key=reusable_captcha_key(),
            seed=reusable_captcha_seed(),
            expires_at=(timezone.now() + datetime.timedelta(days=1)),
        )

        response = self.client.post(
            "/api/registration",
            {
                "email": "test@test.com",
                "password": "password",
                "captcha": f"{captcha.key}:{captcha.secret_phrase}",
            },
        )
        self.assertEqual(response.status_code, 422, response.content)

    def test_RegisterView_post_badcaptcha(self):
        response = self.client.post(
            "/api/registration",
            {
                "email": "test@test.com",
                "password": "aC0mplic?tedTestPassword",
                "captcha": ("a" * 43) + ":badsecretphrase",
            },
        )
        self.assertEqual(response.status_code, 404, response.content)

        captcha = Captcha.objects.create(
            key=reusable_captcha_key(),
            seed=reusable_captcha_seed(),
            expires_at=(timezone.now() + datetime.timedelta(days=1)),
        )

        response = self.client.post(
            "/api/registration",
            {
                "email": "test@test.com",
                "password": "aC0mplic?tedTestPassword",
                "captcha": f"{captcha.key}:badsecretphrase",
            },
        )
        self.assertEqual(response.status_code, 422, response.content)

    def test_VerifyEmailView_post(self):
        user = User.objects.create_user("test@test.com", None)

        email_address = EmailAddress.objects.create(
            user=user, email="test@test.com", primary=True, verified=False
        )

        email_confirmation_hmac = EmailConfirmationHMAC(email_address)

        response = self.client.post(
            "/api/registration/verifyemail",
            {
                "key": email_confirmation_hmac.key,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("detail", json_)
        self.assertIsInstance(json_["detail"], str)

    def test_ResendEmailVerificationView_post(self):
        initial_outbox_count = len(getattr(mail, "outbox", []))

        user = User.objects.create_user("test@test.com", None)

        EmailAddress.objects.create(
            user=user, email="test@test.com", primary=True, verified=False
        )

        response = self.client.post(
            "/api/registration/resendemail",
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
