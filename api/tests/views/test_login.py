import logging

import ujson

from api.models import FacebookLogin, GoogleLogin, User
from api.tests.views import ViewTestCase


class LoginTestCase(ViewTestCase):
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
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": "mypassword",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_my_login_post_email_missing(self):
        response = self.client.post(
            "/api/login/my",
            ujson.dumps(
                {
                    "password": "mypassword",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"missing", response.content)

    def test_my_login_post_email_typeerror(self):
        response = self.client.post(
            "/api/login/my",
            ujson.dumps(
                {
                    "email": True,
                    "password": "mypassword",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"must be", response.content)

    def test_my_login_post_email_malformed(self):
        response = self.client.post(
            "/api/login/my",
            ujson.dumps(
                {
                    "email": "bademail",
                    "password": "mypassword",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"malformed", response.content)

    def test_my_login_post_password_missing(self):
        response = self.client.post(
            "/api/login/my",
            ujson.dumps(
                {
                    "email": "test@test.com",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"missing", response.content)

    def test_my_login_post_password_typeerror(self):
        response = self.client.post(
            "/api/login/my",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": True,
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"must be", response.content)

    def test_my_login_post_already_exists(self):
        User.objects.create_user("test@test.com", "mypassword")

        response = self.client.post(
            "/api/login/my",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": "mypassword",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 409, response.content)

    def test_google_login_post(self):
        with self.settings(GOOGLE_TEST_ID="googleid"):
            response = self.client.post(
                "/api/login/google",
                ujson.dumps(
                    {
                        "email": "test@test.com",
                        "password": "mypassword",
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )
            self.assertEqual(response.status_code, 204, response.content)

    def test_google_login_post_duplicate_login(self):
        user1 = User.objects.create_user("test1@test.com", None)
        GoogleLogin.objects.create(g_user_id="googleid1", user=user1)

        User.objects.create_user("test2@test.com", "password1")

        with self.settings(GOOGLE_TEST_ID="googleid1"):
            response = self.client.post(
                "/api/login/google",
                ujson.dumps(
                    {
                        "email": "test1@test.com",
                        "password": "mypassword",
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )
            self.assertEqual(response.status_code, 409, response.content)

        with self.settings(GOOGLE_TEST_ID="googleid"):
            response = self.client.post(
                "/api/login/google",
                ujson.dumps(
                    {
                        "email": "test2@test.com",
                        "password": "mypassword",
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )
            self.assertEqual(response.status_code, 409, response.content)

    def test_google_login_post_email_missing(self):
        response = self.client.post(
            "/api/login/google",
            ujson.dumps(
                {
                    "password": "mypassword",
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"missing", response.content)

    def test_google_login_post_email_typeerror(self):
        response = self.client.post(
            "/api/login/google",
            ujson.dumps(
                {
                    "email": True,
                    "password": "mypassword",
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"must be", response.content)

    def test_google_login_post_email_malformed(self):
        response = self.client.post(
            "/api/login/google",
            ujson.dumps(
                {
                    "email": "bademail",
                    "password": "mypassword",
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"malformed", response.content)

    def test_google_login_post_password_missing(self):
        response = self.client.post(
            "/api/login/google",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"missing", response.content)

    def test_google_login_post_password_typeerror(self):
        response = self.client.post(
            "/api/login/google",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": True,
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"must be", response.content)

    def test_google_login_post_token_missing(self):
        response = self.client.post(
            "/api/login/google",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": "mypassword",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"missing", response.content)

    def test_google_login_post_token_typeerror(self):
        response = self.client.post(
            "/api/login/google",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": "mypassword",
                    "token": True,
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"must be", response.content)

    def test_facebook_login_post(self):
        with self.settings(FACEBOOK_TEST_ID="facebookid"):
            response = self.client.post(
                "/api/login/facebook",
                ujson.dumps(
                    {
                        "email": "test@test.com",
                        "password": "mypassword",
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )
            self.assertEqual(response.status_code, 204, response.content)

    def test_facebook_login_post_duplicate_login(self):
        user1 = User.objects.create_user("test1@test.com", None)
        FacebookLogin.objects.create(profile_id="facebookid1", user=user1)

        User.objects.create_user("test2@test.com", "password1")

        with self.settings(FACEBOOK_TEST_ID="facebookid1"):
            response = self.client.post(
                "/api/login/facebook",
                ujson.dumps(
                    {
                        "email": "test1@test.com",
                        "password": "mypassword",
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )
            self.assertEqual(response.status_code, 409, response.content)

        with self.settings(FACEBOOK_TEST_ID="facebookid"):
            response = self.client.post(
                "/api/login/facebook",
                ujson.dumps(
                    {
                        "email": "test2@test.com",
                        "password": "mypassword",
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )
            self.assertEqual(response.status_code, 409, response.content)

    def test_facebook_login_post_email_missing(self):
        response = self.client.post(
            "/api/login/facebook",
            ujson.dumps(
                {
                    "password": "mypassword",
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"missing", response.content)

    def test_facebook_login_post_email_typeerror(self):
        response = self.client.post(
            "/api/login/facebook",
            ujson.dumps(
                {
                    "email": True,
                    "password": "mypassword",
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"must be", response.content)

    def test_facebook_login_post_email_malformed(self):
        response = self.client.post(
            "/api/login/facebook",
            ujson.dumps(
                {
                    "email": "bademail",
                    "password": "mypassword",
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"malformed", response.content)

    def test_facebook_login_post_password_missing(self):
        response = self.client.post(
            "/api/login/facebook",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"missing", response.content)

    def test_facebook_login_post_password_typeerror(self):
        response = self.client.post(
            "/api/login/facebook",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": True,
                    "token": "goodtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"must be", response.content)

    def test_facebook_login_post_token_missing(self):
        response = self.client.post(
            "/api/login/facebook",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": "mypassword",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"missing", response.content)

    def test_facebook_login_post_token_typeerror(self):
        response = self.client.post(
            "/api/login/facebook",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": "mypassword",
                    "token": True,
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"must be", response.content)

    def test_my_login_session_post(self):
        User.objects.create_user("test@test.com", "mypassword")

        response = self.client.post(
            "/api/login/my/session",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": "mypassword",
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 204, response.content)

    def test_my_login_session_post_email_missing(self):
        response = self.client.post(
            "/api/login/my/session",
            ujson.dumps(
                {
                    "password": "mypassword",
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"missing", response.content)

    def test_my_login_session_post_email_typeerror(self):
        response = self.client.post(
            "/api/login/my/session",
            ujson.dumps(
                {
                    "email": True,
                    "password": "mypassword",
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"email", response.content)
        self.assertIn(b"must be", response.content)

    def test_my_login_session_post_password_missing(self):
        response = self.client.post(
            "/api/login/my/session",
            ujson.dumps(
                {
                    "email": "test@test.com",
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"missing", response.content)

    def test_my_login_session_post_password_typeerror(self):
        response = self.client.post(
            "/api/login/my/session",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": True,
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"password", response.content)
        self.assertIn(b"must be", response.content)

    def test_my_login_session_post_no_user(self):
        response = self.client.post(
            "/api/login/my/session",
            ujson.dumps(
                {
                    "email": "bademail@test.com",
                    "password": "mypassword",
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 403, response.content)

    def test_my_login_session_post_bad_password(self):
        User.objects.create_user("test@test.com", "mypassword")

        response = self.client.post(
            "/api/login/my/session",
            ujson.dumps(
                {
                    "email": "test@test.com",
                    "password": "badpassword",
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 403, response.content)

    def test_google_login_session_post(self):
        user = User.objects.create_user("test@test.com", None)
        GoogleLogin.objects.create(user=user, g_user_id="googleid")

        with self.settings(GOOGLE_TEST_ID="googleid"):
            response = self.client.post(
                "/api/login/google/session",
                ujson.dumps(
                    {
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )

            self.assertEqual(response.status_code, 204, response.content)

    def test_google_login_session_post_create(self):
        with self.settings(GOOGLE_TEST_ID="googleid"):
            response = self.client.post(
                "/api/login/google/session",
                ujson.dumps(
                    {
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )

            self.assertEqual(response.status_code, 422, response.content)

            json_ = ujson.loads(response.content)

            self.assertIsInstance(json_, dict)
            self.assertIn("token", json_)
            self.assertIn("email", json_)
            self.assertIs(type(json_["token"]), str)
            self.assertTrue(json_["email"] is None or type(json_["email"]) is str)

    def test_google_login_session_post_token_missing(self):
        response = self.client.post(
            "/api/login/google/session", ujson.dumps({}), "application/json"
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"missing", response.content)

    def test_google_login_session_post_token_typeerror(self):
        response = self.client.post(
            "/api/login/google/session",
            ujson.dumps(
                {
                    "token": True,
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"must be", response.content)

    def test_facebook_login_session_post(self):
        user = User.objects.create_user("test@test.com", None)
        FacebookLogin.objects.create(user=user, profile_id="facebookid")

        with self.settings(FACEBOOK_TEST_ID="facebookid"):
            response = self.client.post(
                "/api/login/facebook/session",
                ujson.dumps(
                    {
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )

            self.assertEqual(response.status_code, 204, response.content)

    def test_facebook_login_session_post_create(self):
        with self.settings(FACEBOOK_TEST_ID="facebookid"):
            response = self.client.post(
                "/api/login/facebook/session",
                ujson.dumps(
                    {
                        "token": "goodtoken",
                    }
                ),
                "application/json",
            )

            self.assertEqual(response.status_code, 422, response.content)

            json_ = ujson.loads(response.content)

            self.assertIsInstance(json_, dict)
            self.assertIn("token", json_)
            self.assertIn("email", json_)
            self.assertIs(type(json_["token"]), str)
            self.assertTrue(json_["email"] is None or type(json_["email"]) is str)

    def test_facebook_login_session_post_token_missing(self):
        response = self.client.post(
            "/api/login/facebook/session", ujson.dumps({}), "application/json"
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"missing", response.content)

    def test_facebook_login_session_post_token_typeerror(self):
        response = self.client.post(
            "/api/login/facebook/session",
            ujson.dumps(
                {
                    "token": True,
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"must be", response.content)

    def test_session_delete(self):
        user = User.objects.create_user("test@test.com", None)

        response = self.client.delete("/api/session")
        self.assertEqual(response.status_code, 204, response.content)

        self.client.force_login(user)
        response = self.client.delete("/api/session")
        self.assertEqual(response.status_code, 204, response.content)
