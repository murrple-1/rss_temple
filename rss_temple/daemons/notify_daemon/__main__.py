# Setting up Django

import os

# django.conf.settings requires these be set, but the value doesn't matter
# for this script
os.environ.setdefault('SECRET_KEY', '<SECRET_KEY>')
os.environ.setdefault('PROFILING_OUTPUT_FILE', '')

import django

django.setup()

# Regular scheduled programming

import os
import time

import filelock

from quick_email import send_email

from .impl import logger, render


SMTP_HOST = os.environ['SMTP_HOST']
SMTP_PORT = int(os.environ['SMTP_PORT'])
SMTP_USER = os.environ['SMTP_USER']
SMTP_PASS = os.environ['SMTP_PASS']
SMTP_IS_TLS = os.environ.get('SMTP_IS_TLS', '').lower() == 'true'
SMTP_TIMEOUT = float(os.environ['SMTP_TIMEOUT'])
SMTP_SENDER = os.environ['SMTP_SENDER']

SLEEP_SECONDS = int(os.environ.get('SLEEP_SECONDS', '15'))
COUNT_WARNING_THRESHOLD = int(os.environ.get('COUNT_WARNING_THRESHOLD', '10'))


def send_email_(subject, plain_text=None, html_text=None, send_to=None, send_cc=None, send_bcc=None):
    send_email(
        SMTP_HOST,
        SMTP_PORT,
        SMTP_SENDER,
        subject,
        send_to=send_to,
        send_cc=send_cc,
        send_bcc=send_bcc,
        plain_text=plain_text,
        html_text=html_text,
        username=SMTP_USER,
        password=SMTP_PASS,
        timeout=SMTP_TIMEOUT,
        require_starttls=SMTP_IS_TLS,
    )


lock = filelock.FileLock('notify_daemon.lock')
try:
    with lock.acquire(timeout=1):
        while True:
            logger().debug('render loop started')
            render(send_email_, COUNT_WARNING_THRESHOLD)
            logger().debug('render loop complete')

            time.sleep(SLEEP_SECONDS)
except filelock.Timeout:
    logger().info('only 1 process allowed at a time - lock file already held')
except Exception:
    logger().exception('render loop stopped unexpectedly')
    raise
