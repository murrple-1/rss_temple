import logging
import re
import smtplib

from django.test import TestCase

from api.management.commands.notify_daemon import _logger, render
from api.models import NotifyEmailQueueEntry, NotifyEmailQueueEntryRecipient


def _mock_send_email(*args, **kwargs):
    pass


COUNT_WARNING_THRESHOLD = 10


class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_logger_level = _logger.getEffectiveLevel()

        _logger.setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        _logger.setLevel(cls.old_logger_level)

    def test_render_empty(self):
        self.assertEqual(NotifyEmailQueueEntry.objects.count(), 0)
        render(_mock_send_email, COUNT_WARNING_THRESHOLD)

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
        render(_mock_send_email, COUNT_WARNING_THRESHOLD)
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

        with self.assertLogs(_logger, logging.ERROR) as cm:
            render(_mock_send_email, COUNT_WARNING_THRESHOLD)

            self.assertGreaterEqual(
                len(
                    [
                        line
                        for line in cm.output
                        if re.search(r"SMTP server disconnected", line)
                    ]
                ),
                1,
            )

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

        with self.assertLogs(_logger, logging.ERROR) as cm:
            render(_mock_send_email, COUNT_WARNING_THRESHOLD)

            self.assertGreaterEqual(
                len(
                    [
                        line
                        for line in cm.output
                        if re.search(r"error sending email notification", line)
                    ]
                ),
                1,
            )

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

        with self.assertLogs(_logger, logging.WARNING) as cm:
            render(_mock_send_email, 1)

            self.assertGreaterEqual(
                len(
                    [
                        line
                        for line in cm.output
                        if re.search(
                            r"still more email queue entries than expected", line
                        )
                    ]
                ),
                1,
            )
