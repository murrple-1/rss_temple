import logging
from typing import ClassVar

from django.contrib.sites.models import Site
from rest_framework.test import APITestCase

from api.models import User


class SocialTestCase(APITestCase):
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

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        site = Site.objects.get_current()

        # TODO setup ids and secrets
        site.socialapp_set.create(
            provider="google", name="Google", client_id="", secret=""
        )

        site.socialapp_set.create(
            provider="facebook", name="Facebook", client_id="", secret=""
        )

    def test_SocialAccountListView_get(self):
        user = User.objects.create_user("test@test.com", None)

        self.client.force_authenticate(user=user)

        response = self.client.get("/api/social")
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), list)
        self.assertEqual(len(json_), 0)

    # TODO login, connect and disconnect tests
