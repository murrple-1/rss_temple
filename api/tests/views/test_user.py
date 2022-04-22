import datetime
import logging
import uuid

import ujson
from django.test import tag
from django.utils import timezone

from api.models import User, VerificationToken
from api.tests.views import ViewTestCase


@tag("views")
class UserTestCase(ViewTestCase):
    USER_EMAIL = "test@test.com"
    NON_UNIQUE_EMAIL = "nonunique@test.com"
    UNIQUE_EMAIL = "unique@test.com"

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

        User.objects.create_user(UserTestCase.NON_UNIQUE_EMAIL, "password2")

    def setUp(self):
        super().setUp()

        self.client.login(
            email=UserTestCase.USER_EMAIL, password=UserTestCase.USER_PASSWORD
        )

    def test_user_get(self):
        response = self.client.get("/api/user")
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)

        self.assertIn("subscribedFeedUuids", json_)

    def test_user_put_email(self):
        body = {
            "email": UserTestCase.UNIQUE_EMAIL,
        }

        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        self.assertEqual(
            User.objects.filter(
                uuid=UserTestCase.user.uuid, email=UserTestCase.USER_EMAIL
            ).count(),
            0,
        )
        self.assertEqual(
            User.objects.filter(
                uuid=UserTestCase.user.uuid, email=UserTestCase.UNIQUE_EMAIL
            ).count(),
            1,
        )

    def test_user_put_email_sameasbefore(self):
        body = {
            "email": UserTestCase.USER_EMAIL,
        }

        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        self.assertEqual(
            User.objects.filter(
                uuid=UserTestCase.user.uuid, email=UserTestCase.USER_EMAIL
            ).count(),
            1,
        )

    def test_user_put_email_typeerror(self):
        body = {
            "email": 1,
        }

        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_email_empty(self):
        body = {
            "email": "",
        }

        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_email_malformed(self):
        body = {
            "email": "malformed",
        }

        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_email_nonunique(self):
        body = {
            "email": UserTestCase.NON_UNIQUE_EMAIL,
        }

        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409, response.content)

    def test_user_verify_post(self):
        verification_token = VerificationToken.objects.create(
            expires_at=(timezone.now() + datetime.timedelta(days=2)),
            user=UserTestCase.user,
        )

        response = self.client.post(
            f"/api/user/verify?token={verification_token.token_str}"
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_user_verify_post_token_missing(self):
        response = self.client.post("/api/user/verify")
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_verify_post_token_malformed(self):
        response = self.client.post("/api/user/verify?token=BAD_TOKEN")
        self.assertEqual(response.status_code, 404, response.content)

    def test_user_verify_post_token_notfound(self):
        response = self.client.post(f"/api/user/verify?token={uuid.uuid4()}")
        self.assertEqual(response.status_code, 404, response.content)

    def test_user_attributes_put(self):
        body = {
            "test": "test_string",
        }
        response = self.client.put(
            "/api/user/attributes",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        UserTestCase.user.refresh_from_db()
        self.assertIn("test", UserTestCase.user.attributes)
        self.assertEqual(UserTestCase.user.attributes["test"], "test_string")

    def test_user_attributes_put_deletekeys(self):
        UserTestCase.user.attributes["test"] = "test_string"
        UserTestCase.user.save()
        UserTestCase.user.refresh_from_db()
        self.assertIn("test", UserTestCase.user.attributes)
        self.assertEqual(UserTestCase.user.attributes["test"], "test_string")

        body = {
            "test": None,
        }

        response = self.client.put(
            "/api/user/attributes",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        UserTestCase.user.refresh_from_db()
        self.assertNotIn("test", UserTestCase.user.attributes)
