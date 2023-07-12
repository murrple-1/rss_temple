import logging
from typing import ClassVar

from rest_framework.test import APITestCase


class AuthTestCase(APITestCase):
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

    def test_RegisterView(self):
        response = self.client.post(
            "/api/registration",
            {
                "email": "test@test.com",
                "password1": "aC0mplic?tedTestPassword",
                "password2": "aC0mplic?tedTestPassword",
            },
        )
        self.assertEqual(response.status_code, 204, response.content)
