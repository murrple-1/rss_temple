import datetime
import logging
import uuid

from django.utils import timezone

from api.models import PasswordResetToken, User
from api.tests.views import ViewTestCase


class UserTestCase(ViewTestCase):
    USER_EMAIL = "test@test.com"

    USER_PASSWORD = "password"

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
            UserTestCase.USER_EMAIL, UserTestCase.USER_PASSWORD
        )

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
            "email": UserTestCase.USER_EMAIL,
        }
        response = self.client.post("/api/passwordresettoken/request", params)
        self.assertEqual(response.status_code, 204, response.content)

    def test_passwordresettoken_reset_post(self):
        response = self.client.post("/api/passwordresettoken/reset")
        self.assertEqual(response.status_code, 400, response.content)

        params = {}
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "token": "",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            "token": "",
            "password": "",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 404, response.content)

        params = {
            "token": "badtoken",
            "password": "newpassword",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 404, response.content)

        params = {
            "token": str(uuid.uuid4()),
            "password": "newpassword",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 404, response.content)

        password_reset_token = PasswordResetToken.objects.create(
            expires_at=(timezone.now() + datetime.timedelta(days=2)),
            user=UserTestCase.user,
        )

        params = {
            "token": password_reset_token.token_str(),
            "password": "newpassword",
        }
        response = self.client.post("/api/passwordresettoken/reset", params)
        self.assertEqual(response.status_code, 204, response.content)
