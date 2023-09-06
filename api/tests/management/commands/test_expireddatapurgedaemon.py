import datetime
import logging
from io import StringIO
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from api.management.commands.expireddatapurgedaemon import Command
from api.models import Captcha

if TYPE_CHECKING:
    from unittest.mock import _Mock, _patch


class DaemonTestCase(TestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]

    command: ClassVar[Command]
    stdout_patcher: ClassVar["_patch[_Mock]"]
    stderr_patcher: ClassVar["_patch[_Mock]"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)
        logging.getLogger("django").setLevel(logging.CRITICAL)

        cls.command = Command()
        cls.stdout_patcher = patch.object(cls.command, "stdout", new_callable=StringIO)
        cls.stderr_patcher = patch.object(cls.command, "stderr", new_callable=StringIO)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    def setUp(self):
        super().setUp()

        self.stdout_patcher.start()
        self.stderr_patcher.start()

    def tearDown(self):
        super().tearDown()

        self.stdout_patcher.stop()
        self.stderr_patcher.stop()

    def test_purge(self):
        now = timezone.now()

        Captcha.objects.create(
            key="testkey1",
            seed="testseed1",
            expires_at=(now + datetime.timedelta(days=1)),
        )
        Captcha.objects.create(
            key="testkey2",
            seed="testseed2",
            expires_at=(now + datetime.timedelta(days=-1)),
        )

        self.assertEqual(Captcha.objects.count(), 2)

        msgs = DaemonTestCase.command._purge()
        self.assertIn("removed 1 captchas", msgs)

        self.assertEqual(Captcha.objects.count(), 1)

    # TODO write tests
