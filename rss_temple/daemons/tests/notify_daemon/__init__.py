import logging
import re
import smtplib

from api import models
from daemons.notify_daemon.impl import logger, render
from django.test import TestCase


def _mock_send_email(*args, **kwargs):
    pass


COUNT_WARNING_THRESHOLD = 10


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

    def test_render_empty(self):
        self.assertEqual(models.NotifyEmailQueueEntry.objects.count(), 0)
        render(_mock_send_email, COUNT_WARNING_THRESHOLD)

    def test_render_regular(self):
        email_entry = models.NotifyEmailQueueEntry.objects.create(
            subject="Subject", plain_text="Some Text", html_text="<b>Some Text</b>"
        )
        models.NotifyEmailQueueEntryRecipient.objects.create(
            type=models.NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry,
        )
        models.NotifyEmailQueueEntryRecipient.objects.create(
            type=models.NotifyEmailQueueEntryRecipient.TYPE_CC,
            email="cc@test.com",
            entry=email_entry,
        )
        models.NotifyEmailQueueEntryRecipient.objects.create(
            type=models.NotifyEmailQueueEntryRecipient.TYPE_BCC,
            email="bcc@test.com",
            entry=email_entry,
        )

        self.assertEqual(models.NotifyEmailQueueEntry.objects.count(), 1)
        render(_mock_send_email, COUNT_WARNING_THRESHOLD)
        self.assertEqual(models.NotifyEmailQueueEntry.objects.count(), 0)

    def test_render_smtpdisconnected(self):
        email_entry = models.NotifyEmailQueueEntry.objects.create(
            subject="Subject", plain_text="Some Text", html_text="<b>Some Text</b>"
        )
        models.NotifyEmailQueueEntryRecipient.objects.create(
            type=models.NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry,
        )

        def _mock_send_email(*args, **kwargs):
            raise smtplib.SMTPServerDisconnected()

        with self.assertLogs(logger(), logging.ERROR) as cm:
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
        email_entry = models.NotifyEmailQueueEntry.objects.create(
            subject="Subject", plain_text="Some Text", html_text="<b>Some Text</b>"
        )
        models.NotifyEmailQueueEntryRecipient.objects.create(
            type=models.NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry,
        )

        def _mock_send_email(*args, **kwargs):
            raise Exception()

        with self.assertLogs(logger(), logging.ERROR) as cm:
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
        email_entry1 = models.NotifyEmailQueueEntry.objects.create(
            subject="Subject1", plain_text="Some Text1", html_text="<b>Some Text1</b>"
        )
        models.NotifyEmailQueueEntryRecipient.objects.create(
            type=models.NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry1,
        )

        email_entry2 = models.NotifyEmailQueueEntry.objects.create(
            subject="Subject2", plain_text="Some Text2", html_text="<b>Some Text2</b>"
        )
        models.NotifyEmailQueueEntryRecipient.objects.create(
            type=models.NotifyEmailQueueEntryRecipient.TYPE_TO,
            email="to@test.com",
            entry=email_entry2,
        )

        def _mock_send_email(*args, **kwargs):
            raise Exception()

        with self.assertLogs(logger(), logging.WARNING) as cm:
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
