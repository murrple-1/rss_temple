import datetime
import logging

from django.test import TestCase
from django.utils import timezone

from api import models
from daemons.session_cleanup_daemon.impl import cleanup, logger


class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_logger_level = logger().getEffectiveLevel()

        logger().setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logger().setLevel(cls.old_logger_level)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = models.User.objects.create(email="test@test.com")

    def test_none(self):
        user = DaemonTestCase.user

        self.assertEqual(models.Session.objects.filter(user=user).count(), 0)

        cleanup()

        self.assertEqual(models.Session.objects.filter(user=user).count(), 0)

    def test_some(self):
        user = DaemonTestCase.user

        self.assertEqual(models.Session.objects.filter(user=user).count(), 0)

        models.Session.objects.create(
            expires_at=timezone.now() + datetime.timedelta(days=-1),
            user=user,
        )

        models.Session.objects.create(
            expires_at=timezone.now() + datetime.timedelta(days=1),
            user=user,
        )

        self.assertEqual(models.Session.objects.filter(user=user).count(), 2)

        cleanup()

        self.assertEqual(models.Session.objects.filter(user=user).count(), 1)
