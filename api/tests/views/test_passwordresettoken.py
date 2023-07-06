import datetime
import logging
import uuid
from typing import Any, ClassVar

from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import PasswordResetToken, User


class PasswordResetTokenTestCase(APITestCase):
    USER_EMAIL = "test@test.com"

    USER_PASSWORD = "password"

    old_django_logger_level: ClassVar[int]
    user: ClassVar[User]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("django").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user(
            PasswordResetTokenTestCase.USER_EMAIL,
            PasswordResetTokenTestCase.USER_PASSWORD,
        )

    def test_passwordresettoken_request_post(self):
        response = self.client.post("/api/passwordresettoken/request")
        self.assertEqual(response.status_code, 400, response.content)

        params: dict[str, Any] = {}
        response = self.client.post(
            "/api/passwordresettoken/request", params, format="multipart"
        )
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "email": "",
        }
        response = self.client.post(
            "/api/passwordresettoken/request", params, format="multipart"
        )
        self.assertEqual(response.status_code, 204, response.content)

        params = {
            "email": "malformedemail",
        }
        response = self.client.post(
            "/api/passwordresettoken/request", params, format="multipart"
        )
        self.assertEqual(response.status_code, 204, response.content)

        params = {
            "email": "unknownemail@test.com",
        }
        response = self.client.post(
            "/api/passwordresettoken/request", params, format="multipart"
        )
        self.assertEqual(response.status_code, 204, response.content)

        params = {
            "email": PasswordResetTokenTestCase.USER_EMAIL,
        }
        response = self.client.post(
            "/api/passwordresettoken/request", params, format="multipart"
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_passwordresettoken_reset_post(self):
        response = self.client.post("/api/passwordresettoken/reset")
        self.assertEqual(response.status_code, 400, response.content)

        params: dict[str, Any] = {}
        response = self.client.post(
            "/api/passwordresettoken/reset", params, format="multipart"
        )
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "token": "",
        }
        response = self.client.post(
            "/api/passwordresettoken/reset", params, format="multipart"
        )
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "token": "",
            "password": "",
        }
        response = self.client.post(
            "/api/passwordresettoken/reset", params, format="multipart"
        )
        self.assertEqual(response.status_code, 404, response.content)

        params = {
            "token": "badtoken",
            "password": "newpassword",
        }
        response = self.client.post(
            "/api/passwordresettoken/reset", params, format="multipart"
        )
        self.assertEqual(response.status_code, 404, response.content)

        params = {
            "token": str(uuid.uuid4()),
            "password": "newpassword",
        }
        response = self.client.post(
            "/api/passwordresettoken/reset", params, format="multipart"
        )
        self.assertEqual(response.status_code, 404, response.content)

        password_reset_token = PasswordResetToken.objects.create(
            expires_at=(timezone.now() + datetime.timedelta(days=2)),
            user=PasswordResetTokenTestCase.user,
        )

        params = {
            "token": password_reset_token.token_str(),
            "password": "newpassword",
        }
        response = self.client.post(
            "/api/passwordresettoken/reset", params, format="multipart"
        )
        self.assertEqual(response.status_code, 204, response.content)
