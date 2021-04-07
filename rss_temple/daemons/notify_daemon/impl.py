import sys
import logging
import smtplib

from django.db import transaction

import validators

from api import models


_logger = None


def logger():
    global _logger

    if _logger is None:
        _logger = logging.getLogger('notify_daemon')
        _logger.setLevel(logging.DEBUG)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(stream_handler)

        file_handler = logging.handlers.RotatingFileHandler(
            filename='notify_daemon.log', maxBytes=(
                50 * 100000), backupCount=3)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(file_handler)

    return _logger


def render(send_email_fn, count_warning_threshold):
    entry_count = 0
    with transaction.atomic():
        for notify_email_queue_entry in models.NotifyEmailQueueEntry.objects.select_for_update(skip_locked=True).all():
            try:
                send_to = []
                send_cc = []
                send_bcc = []

                for recipient in models.NotifyEmailQueueEntryRecipient.objects.filter(entry=notify_email_queue_entry):
                    if validators.email(recipient.email):
                        if recipient.type == models.NotifyEmailQueueEntryRecipient.TYPE_TO:
                            send_to.append(recipient.email)
                        elif recipient.type == models.NotifyEmailQueueEntryRecipient.TYPE_CC:
                            send_cc.append(recipient.email)
                        elif recipient.type == models.NotifyEmailQueueEntryRecipient.TYPE_BCC:
                            send_bcc.append(recipient.email)

                logger().debug('sending email to %s, %s, %s...', send_to, send_cc, send_bcc)

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
                logger().error('SMTP server disconnected: %s', e)
            except Exception:
                logger().exception('error sending email notification: %s', notify_email_queue_entry.uuid)
            else:
                entry_count += 1
                notify_email_queue_entry.delete()

    if entry_count > 0:
        logger().info('completed %s notify queue entries', entry_count)
    else:
        logger().info('no notify queue entries found')

    email_count = models.NotifyEmailQueueEntry.objects.count()
    if email_count >= count_warning_threshold:
        logger().warning('still more email queue entries than expected: %d (threshold: %d)',
                         email_count, count_warning_threshold)
