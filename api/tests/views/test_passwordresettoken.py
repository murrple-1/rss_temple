import logging

from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase

from api.models import User


class UserTestCase(TestCase):
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

        cls.user = User.objects.create_user("test@test.com", "password")

    def test_passwordresettoken_request_post(self):
        response = self.client.post("/api/passwordresettoken/request")
        self.assertEqual(response.status_code, 400, response.content)

        params = {}
        response = self.client.post("/api/passwordresettoken/request", params)
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "email": "",
        }
        response = self.client.post("/api/passwordresettoken/request", params)
        self.assertEqual(response.status_code, 204, response.content)

        params = {
            "email": "malformedemail",
        }
        response = self.client.post("/api/passwordresettoken/request", params)
        self.assertEqual(response.status_code, 204, response.content)

        params = {
            "email": "unknownemail@test.com",
        }
        response = self.client.post("/api/passwordresettoken/request", params)
        self.assertEqual(response.status_code, 204, response.content)

        params = {
            "email": "test@test.com",
        }
        response = self.client.post("/api/passwordresettoken/request", params)
        self.assertEqual(response.status_code, 204, response.content)

    def test_passwordresettoken_reset_post(self):
        response = self.client.post("/api/passwordresettoken/reset")
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "email": "",
            "password": "",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "token": "",
            "password": "",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "token": "",
            "password": "",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "token": "badtoken",
            "password": "newpassword",
            "email": "test@test.com",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 404, response.content)

        params = {
            "token": "badtoken",
            "password": "newpassword",
            "email": "bademail@test.com",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 404, response.content)

        token_str = default_token_generator.make_token(UserTestCase.user)

        params = {
            "token": token_str,
            "password": "newpassword",
            "email": "test@test.com",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 204, response.content)
