import datetime
import logging
import uuid
from typing import ClassVar

import ujson
from django.utils import timezone

from api import fields
from api.models import FacebookLogin, GoogleLogin, User, VerificationToken
from api.tests.views import ViewTestCase


class UserTestCase(ViewTestCase):
    USER_EMAIL = "test@test.com"
    NON_UNIQUE_EMAIL = "nonunique@test.com"
    UNIQUE_EMAIL = "unique@test.com"

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
            UserTestCase.USER_EMAIL, UserTestCase.USER_PASSWORD
        )

        User.objects.create_user(UserTestCase.NON_UNIQUE_EMAIL, "password2")

    def setUp(self):
        super().setUp()

        UserTestCase.user.refresh_from_db()

        self.client.force_login(UserTestCase.user)

    def test_user_get(self):
        self.client.force_login(UserTestCase.user)

        response = self.client.get(
            "/api/user",
            {"fields": ",".join(fields.field_list("user"))},
        )
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
        self.assertEqual(response.status_code, 204, response.content)

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
        self.assertEqual(response.status_code, 204, response.content)

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

    def test_user_put_my(self):
        body = {
            "my": {},
        }

        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_user_put_my_typeerror(self):
        body = {
            "my": None,
        }

        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_my_password(self):
        body = {
            "my": {
                "password": {
                    "old": UserTestCase.USER_PASSWORD,
                    "new": "newpassword",
                },
            },
        }

        old_password_hash = UserTestCase.user.password

        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        UserTestCase.user.refresh_from_db()
        new_password_hash = UserTestCase.user.password

        self.assertNotEqual(old_password_hash, new_password_hash)

    def test_user_put_my_password_typeerror(self):
        body = {
            "my": {
                "password": None,
            },
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_my_password_old_missing(self):
        body = {
            "my": {
                "password": {
                    "new": "newpassword",
                },
            },
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_my_password_old_typeerror(self):
        body = {
            "my": {
                "password": {
                    "old": None,
                    "new": "newpassword",
                },
            },
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_my_password_new_missing(self):
        body = {
            "my": {
                "password": {
                    "old": UserTestCase.USER_PASSWORD,
                },
            },
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_my_password_new_typeerror(self):
        body = {
            "my": {
                "password": {
                    "old": UserTestCase.USER_PASSWORD,
                    "new": None,
                },
            },
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_my_password_badoldpassword(self):
        body = {
            "my": {
                "password": {
                    "old": "badpassword",
                    "new": "newpassword",
                },
            },
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403, response.content)

    def test_user_put_google(self):
        body = {
            "google": {},
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_user_put_google_typeerror(self):
        body = {
            "google": 1,
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_google_create(self):
        self.assertEqual(GoogleLogin.objects.filter(user=UserTestCase.user).count(), 0)

        body = {
            "google": {
                "token": "goodtoken",
            },
        }
        with self.settings(GOOGLE_TEST_ID="googleid"):
            response = self.client.put(
                "/api/user",
                ujson.dumps(body),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(GoogleLogin.objects.filter(user=UserTestCase.user).count(), 1)

    def test_user_put_google_delete(self):
        GoogleLogin.objects.create(user=UserTestCase.user, g_user_id="googleid")
        self.assertEqual(GoogleLogin.objects.filter(user=UserTestCase.user).count(), 1)

        body = {
            "google": None,
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(GoogleLogin.objects.filter(user=UserTestCase.user).count(), 0)

    def test_user_put_google_token_typeerror(self):
        body = {
            "google": {
                "token": None,
            },
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_facebook(self):
        body = {
            "facebook": {},
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_user_put_facebook_typeerror(self):
        body = {
            "facebook": 1,
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_put_facebook_create(self):
        self.assertEqual(
            FacebookLogin.objects.filter(user=UserTestCase.user).count(), 0
        )

        body = {
            "facebook": {
                "token": "goodtoken",
            },
        }
        with self.settings(FACEBOOK_TEST_ID="facebookid"):
            response = self.client.put(
                "/api/user",
                ujson.dumps(body),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            FacebookLogin.objects.filter(user=UserTestCase.user).count(), 1
        )

    def test_user_put_facebook_delete(self):
        FacebookLogin.objects.create(user=UserTestCase.user, profile_id="facebookid")
        self.assertEqual(
            FacebookLogin.objects.filter(user=UserTestCase.user).count(), 1
        )

        body = {
            "facebook": None,
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            FacebookLogin.objects.filter(user=UserTestCase.user).count(), 0
        )

    def test_user_put_facebook_token_typeerror(self):
        body = {
            "facebook": {
                "token": None,
            },
        }
        response = self.client.put(
            "/api/user",
            ujson.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_verify_post(self):
        verification_token = VerificationToken.objects.create(
            expires_at=(timezone.now() + datetime.timedelta(days=2)),
            user=UserTestCase.user,
        )

        params = {
            "token": verification_token.token_str(),
        }
        response = self.client.post("/api/user/verify", params)
        self.assertEqual(response.status_code, 204, response.content)

    def test_user_verify_post_token_missing(self):
        response = self.client.post("/api/user/verify")
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_verify_post_token_malformed(self):
        params = {
            "token": "BAD_TOKEN",
        }
        response = self.client.post("/api/user/verify", params)
        self.assertEqual(response.status_code, 404, response.content)

    def test_user_verify_post_token_notfound(self):
        params = {
            "token": str(uuid.uuid4()),
        }
        response = self.client.post("/api/user/verify", params)
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
