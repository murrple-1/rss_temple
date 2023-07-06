import logging
from typing import ClassVar

from rest_framework.test import APITestCase

from api.models import User


class LoginTestCase(APITestCase):
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

    def test_my_login_post(self):
        response = self.client.post(
            "/api/login/my",
            {
                "email": "test@test.com",
                "password": "mypassword",
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_my_login_post_email_missing(self):
        response = self.client.post(
            "/api/login/my",
            {
                "password": "mypassword",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"missing", response.content)

    def test_my_login_post_email_typeerror(self):
        response = self.client.post(
            "/api/login/my",
            {
                "email": True,
                "password": "mypassword",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"must be", response.content)

    def test_my_login_post_email_malformed(self):
        response = self.client.post(
            "/api/login/my",
            {
                "email": "bademail",
                "password": "mypassword",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"malformed", response.content)

    def test_my_login_post_password_missing(self):
        response = self.client.post(
            "/api/login/my",
            {
                "email": "test@test.com",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"missing", response.content)

    def test_my_login_post_password_typeerror(self):
        response = self.client.post(
            "/api/login/my",
            {
                "email": "test@test.com",
                "password": True,
            },
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"must be", response.content)

    def test_my_login_post_already_exists(self):
        User.objects.create_user("test@test.com", "mypassword")

        response = self.client.post(
            "/api/login/my",
            {
                "email": "test@test.com",
                "password": "mypassword",
            },
        )
        self.assertEqual(response.status_code, 409, response.content)
