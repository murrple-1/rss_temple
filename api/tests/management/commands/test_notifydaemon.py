import re
import smtplib
from io import StringIO
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

from django.test import TestCase

from api.management.commands.notifydaemon import Command
from api.models import NotifyEmailQueueEntry, NotifyEmailQueueEntryRecipient

if TYPE_CHECKING:
    from unittest.mock import _Mock, _patch


def _mock_send_email(*args, **kwargs):
    pass


COUNT_WARNING_THRESHOLD = 10


class DaemonTestCase(TestCase):
    command: ClassVar[Command]
    stdout_patcher: ClassVar["_patch[_Mock]"]
    stderr_patcher: ClassVar["_patch[_Mock]"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.command = Command()
        cls.stdout_patcher = patch.object(cls.command, "stdout", new_callable=StringIO)
        cls.stderr_patcher = patch.object(cls.command, "stderr", new_callable=StringIO)

    def setUp(self):
        super().setUp()

        self.stdout_patcher.start()
        self.stderr_patcher.start()

    def tearDown(self):
        super().tearDown()

        self.stdout_patcher.stop()
        self.stderr_patcher.stop()

    def test_render_empty(self):
        self.assertEqual(NotifyEmailQueueEntry.objects.count(), 0)
        self.command._render(_mock_send_email, COUNT_WARNING_THRESHOLD)

    def test_render_regular(self):
        email_entry = NotifyEmailQueueEntry.objects.create(
            subject="Subject", plain_text="Some Text", html_text="<b>Some Text</b>"
        )
        NotifyEmailQueueEntryRecipient.objects.create(
            type=NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry,
        )
        NotifyEmailQueueEntryRecipient.objects.create(
            type=NotifyEmailQueueEntryRecipient.TYPE_CC,
            email="cc@test.com",
            entry=email_entry,
        )
        NotifyEmailQueueEntryRecipient.objects.create(
            type=NotifyEmailQueueEntryRecipient.TYPE_BCC,
            email="bcc@test.com",
            entry=email_entry,
        )

        self.assertEqual(NotifyEmailQueueEntry.objects.count(), 1)
        self.command._render(_mock_send_email, COUNT_WARNING_THRESHOLD)

        self.assertEqual(NotifyEmailQueueEntry.objects.count(), 0)

    def test_render_smtpdisconnected(self):
        email_entry = NotifyEmailQueueEntry.objects.create(
            subject="Subject", plain_text="Some Text", html_text="<b>Some Text</b>"
        )
        NotifyEmailQueueEntryRecipient.objects.create(
            type=NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry,
        )

        def _mock_send_email(*args, **kwargs):
            raise smtplib.SMTPServerDisconnected()

        self.command._render(_mock_send_email, COUNT_WARNING_THRESHOLD)
        stderr_value = self.command.stderr.getvalue()

        matches = re.findall(r"SMTP server disconnected", stderr_value)
        self.assertGreaterEqual(len(matches), 1, stderr_value)

    def test_render_generalerror(self):
        email_entry = NotifyEmailQueueEntry.objects.create(
            subject="Subject", plain_text="Some Text", html_text="<b>Some Text</b>"
        )
        NotifyEmailQueueEntryRecipient.objects.create(
            type=NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry,
        )

        def _mock_send_email(*args, **kwargs):
            raise Exception()

        self.command._render(_mock_send_email, COUNT_WARNING_THRESHOLD)
        stderr_value = self.command.stderr.getvalue()

        matches = re.findall(r"error sending email notification", stderr_value)
        self.assertGreaterEqual(len(matches), 1, stderr_value)

    def test_render_countwarning(self):
        email_entry1 = NotifyEmailQueueEntry.objects.create(
            subject="Subject1", plain_text="Some Text1", html_text="<b>Some Text1</b>"
        )
        NotifyEmailQueueEntryRecipient.objects.create(
            type=NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry1,
        )

        email_entry2 = NotifyEmailQueueEntry.objects.create(
            subject="Subject2", plain_text="Some Text2", html_text="<b>Some Text2</b>"
        )
        NotifyEmailQueueEntryRecipient.objects.create(
            type=NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry2,
        )

        def _mock_send_email(*args, **kwargs):
            raise Exception()

        self.command._render(_mock_send_email, 1)
        stderr_value = self.command.stderr.getvalue()

        matches = re.findall(
            r"still more email queue entries than expected", stderr_value
        )
        self.assertGreaterEqual(len(matches), 1, stderr_value)
