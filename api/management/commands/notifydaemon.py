import functools
import getpass
import smtplib
import time
import traceback
from typing import Any, Protocol

import validators
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from quick_email import send_email

from api.models import NotifyEmailQueueEntry, NotifyEmailQueueEntryRecipient


class _SendEmailCallable(Protocol):
    def __call__(
        self,
        subject: str,
        plain_text: str | None = None,
        html_text: str | None = None,
        send_to: list[str] | None = None,
        send_cc: list[str] | None = None,
        send_bcc: list[str] | None = None,
    ) -> None:
        ...


class Command(BaseCommand):
    help = "Daemon to send out notification from the queue"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("smtp_host")
        parser.add_argument("smtp_port", type=int)
        parser.add_argument("smtp_sender")
        parser.add_argument("-s", "--sleep-seconds", type=int, default=15)
        parser.add_argument("-c", "--count-warning-threshold", type=int, default=10)
        parser.add_argument("--smtp-user")
        parser.add_argument("--smtp-password")
        parser.add_argument("--smtp-password-stdin", action="store_true")
        parser.add_argument("--smtp-is-tls", action="store_true")
        parser.add_argument("--smtp-timeout", type=float)

    def handle(self, *args: Any, **options: Any) -> str | None:
        smtp_password: str | None
        if options["smtp_password"]:
            smtp_password = options["smtp_password"]
        elif options["smtp_password_stdin"]:
            smtp_password = getpass.getpass("SMTP Password: ")
        else:
            smtp_password = None

        try:
            while True:
                self.stderr.write(self.style.NOTICE("render loop started"))
                self._render(
                    functools.partial(
                        self._send_email,
                        options["smtp_host"],
                        options["smtp_port"],
                        options["smtp_sender"],
                        user=options["smtp_user"],
                        password=smtp_password,
                        require_starttls=options["smtp_is_tls"],
                        timeout=options["smtp_timeout"],
                    ),
                    options["count_warning_threshold"],
                )
                self.stderr.write(self.style.NOTICE("render loop complete"))

                time.sleep(options["sleep_seconds"])
        except Exception:
            self.stderr.write(
                self.style.ERROR(
                    f"render loop stopped unexpectedly\n{traceback.format_exc()}"
                )
            )
            raise

    def _send_email(
        self,
        host: str,
        port: int,
        sender: str,
        subject: str,
        plain_text: str | None = None,
        html_text: str | None = None,
        send_to: list[str] | None = None,
        send_cc: list[str] | None = None,
        send_bcc: list[str] | None = None,
        user: str | None = None,
        password: str | None = None,
        require_starttls: bool = False,
        timeout: float | None = None,
    ):
        send_email(
            host,
            port,
            sender,
            subject,
            send_to=send_to,
            send_cc=send_cc,
            send_bcc=send_bcc,
            plain_text=plain_text,
            html_text=html_text,
            username=user,
            password=password,
            timeout=timeout,
            require_starttls=require_starttls,
        )

    def _render(self, send_email_fn: _SendEmailCallable, count_warning_threshold: int):
        entry_count = 0
        with transaction.atomic():
            for (
                notify_email_queue_entry
            ) in NotifyEmailQueueEntry.objects.select_for_update(
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
                            elif (
                                recipient.type == NotifyEmailQueueEntryRecipient.TYPE_CC
                            ):
                                send_cc.append(recipient.email)
                            elif (
                                recipient.type
                                == NotifyEmailQueueEntryRecipient.TYPE_BCC
                            ):
                                send_bcc.append(recipient.email)

                    self.stderr.write(
                        self.style.NOTICE(
                            f"sending email to {send_to}, {send_cc}, {send_bcc}..."
                        )
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
                    self.stderr.write(
                        self.style.ERROR(f"SMTP server disconnected: {e}")
                    )
                except Exception:
                    self.stderr.write(
                        self.style.ERROR(
                            f"error sending email notification: {notify_email_queue_entry.uuid}\n{traceback.format_exc()}"
                        )
                    )

                else:
                    entry_count += 1
                    notify_email_queue_entry.delete()

        if entry_count > 0:
            self.stderr.write(
                self.style.NOTICE(f"completed {entry_count} notify queue entries")
            )
        else:
            self.stderr.write(self.style.NOTICE("no notify queue entries found"))

        email_count = NotifyEmailQueueEntry.objects.count()
        if email_count >= count_warning_threshold:
            self.stderr.write(
                self.style.WARNING(
                    f"still more email queue entries than expected: {email_count} (threshold: {count_warning_threshold})"
                )
            )
