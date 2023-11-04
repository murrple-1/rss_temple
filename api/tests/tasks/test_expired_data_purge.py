import datetime
import logging
import secrets
from typing import ClassVar

from django.test import TestCase
from django.utils import timezone

from api.models import Captcha
from api.tasks.purge_expired_data import purge_expired_data


class TaskTestCase(TestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]

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

    def test_purge_expired_data(self):
        now = timezone.now()

        Captcha.objects.create(
            key=secrets.token_urlsafe(32),
            seed=secrets.token_hex(32),
            expires_at=(now + datetime.timedelta(days=1)),
        )
        Captcha.objects.create(
            key=secrets.token_urlsafe(32),
            seed=secrets.token_hex(32),
            expires_at=(now + datetime.timedelta(days=-1)),
        )

        self.assertEqual(Captcha.objects.count(), 2)

        purge_expired_data()

        self.assertEqual(Captcha.objects.count(), 1)

    # TODO write tests
