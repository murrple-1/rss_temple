import logging
from typing import ClassVar

from rest_framework.test import APITestCase

from api import fields
from api.models import User


class UserTestCase(APITestCase):
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

        self.client.force_authenticate(user=UserTestCase.user)

    def test_user_get(self):
        self.client.force_authenticate(user=UserTestCase.user)

        response = self.client.get(
            "/api/user",
            {"fields": ",".join(fields.field_list("user"))},
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIn("subscribedFeedUuids", json_)

    def test_user_attributes_put(self):
        body = {
            "test": "test_string",
        }
        response = self.client.put(
            "/api/user/attributes",
            body,
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
            body,
        )
        self.assertEqual(response.status_code, 204, response.content)

        UserTestCase.user.refresh_from_db()
        self.assertNotIn("test", UserTestCase.user.attributes)
