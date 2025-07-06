import logging
from typing import ClassVar

from rest_framework.test import APITestCase

from api.models import User
from api.tests.utils import disable_silk, disable_throttling


@disable_silk()
@disable_throttling()
class UserMetaTestCase(APITestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]
    user: ClassVar[User]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)
        logging.getLogger("django").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test@test.com", None)

    def setUp(self):
        super().setUp()

        self.client.force_authenticate(user=UserMetaTestCase.user)

    def test_UserCategoryView_get(self):
        response = self.client.get(
            "/api/user/meta/readcount",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), int)
