import logging
import logging.handlers
import smtplib
import sys
import time

import validators
from django.core.management.base import BaseCommand
from django.db import transaction
from quick_email import send_email

from api.models import NotifyEmailQueueEntry, NotifyEmailQueueEntryRecipient

_logger = logging.getLogger("rss_temple")


def render(send_email_fn, count_warning_threshold):
    entry_count = 0
    with transaction.atomic():
        for notify_email_queue_entry in NotifyEmailQueueEntry.objects.select_for_update(
            skip_locked=True
        ).all():
            try:
                send_to = []
                send_cc = []
                send_bcc = []

                for recipient in NotifyEmailQueueEntryRecipient.objects.filter(
                    entry=notify_email_queue_entry
                ):
                    if validators.email(recipient.email):
                        if recipient.type == NotifyEmailQueueEntryRecipient.TYPE_TO:
                            send_to.append(recipient.email)
                        elif recipient.type == NotifyEmailQueueEntryRecipient.TYPE_CC:
                            send_cc.append(recipient.email)
                        elif recipient.type == NotifyEmailQueueEntryRecipient.TYPE_BCC:
                            send_bcc.append(recipient.email)

                _logger.debug(
                    "sending email to %s, %s, %s...", send_to, send_cc, send_bcc
                )

                if len(send_to) > 0 or len(send_cc) > 0 or len(send_bcc) > 0:
                    send_email_fn(
                        notify_email_queue_entry.subject,
                        send_to=send_to,
                        send_cc=send_cc,
                        send_bcc=send_bcc,
                        plain_text=notify_email_queue_entry.plain_text,
                        html_text=notify_email_queue_entry.html_text,
                    )
            except smtplib.SMTPServerDisconnected as e:
                _logger.error("SMTP server disconnected: %s", e)
            except Exception:
                _logger.exception(
                    "error sending email notification: %s",
                    notify_email_queue_entry.uuid,
                )
            else:
                entry_count += 1
                notify_email_queue_entry.delete()

    if entry_count > 0:
        _logger.info("completed %s notify queue entries", entry_count)
    else:
        _logger.info("no notify queue entries found")

    email_count = NotifyEmailQueueEntry.objects.count()
    if email_count >= count_warning_threshold:
        _logger.warning(
            "still more email queue entries than expected: %d (threshold: %d)",
            email_count,
            count_warning_threshold,
        )


class Command(BaseCommand):
    help = "TODO helptext"

    def add_arguments(self, parser):
        parser.add_argument("-s", "--sleep-seconds", type=int, default=15)
        parser.add_argument("-w", "--count-warning-threshold", type=int, default=10)
        parser.add_argument("-t", "--smtp-is-tls", action="store_true")

        parser.add_argument("smtp_host")
        parser.add_argument("smtp_port", type=int)
        parser.add_argument("smtp_user")
        parser.add_argument("smtp_pass")
        parser.add_argument("smtp_timeout", type=float)
        parser.add_argument("smtp_sender")

    def handle(self, *args, **options):
        def _send_email(
            subject,
            plain_text=None,
            html_text=None,
            send_to=None,
            send_cc=None,
            send_bcc=None,
        ):
            send_email(
                options["smtp_host"],
                options["smtp_port"],
                options["smtp_sender"],
                subject,
                send_to=send_to,
                send_cc=send_cc,
                send_bcc=send_bcc,
                plain_text=plain_text,
                html_text=html_text,
                username=options["smtp_user"],
                password=options["smtp_pass"],
                timeout=options["smtp_timeout"],
                require_starttls=options["smtp_is_tls"],
            )

        try:
            while True:
                _logger.debug("render loop started")
                render(send_email, options["count_warning_threshold"])
                _logger.debug("render loop complete")

                time.sleep(options["sleep_seconds"])
        except Exception:
            _logger.exception("render loop stopped unexpectedly")
            raise
