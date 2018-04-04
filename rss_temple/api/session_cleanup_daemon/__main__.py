# Setting up Django

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rss_temple.settings')

# django.conf.settings requires these be set, but the value doesn't matter
# for this script
os.environ.setdefault('SECRET_KEY', '<SECRET_KEY>')

import django

django.setup()

# Regular scheduled programming

import logging
import sys
import time
import argparse

from django.db.models.functions import Now

import filelock

from api import models

_logger = None


def logger():
    global _logger

    if _logger is None:
        _logger = logging.getLogger(__name__)
        _logger.setLevel(logging.DEBUG)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(stream_handler)

        file_handler = logging.handlers.RotatingFileHandler(
            filename='session_cleanup_daemon.log', maxBytes=(
                50 * 100000), backupCount=3)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(file_handler)

    return _logger


def cleanup():
    count, _ = models.Session.objects.filter(expires_at__lt=Now()).delete()

    if count > 0:
        logger().debug('deleting %s sessions', count)
    else:
        logger().debug('no sessions deleted')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--force-now',
        help='Clear the expired sessions immediately, then exit',
        action='store_true',
        dest='runNow')
    args = parser.parse_args()

    if not args.runNow:
        lock = filelock.FileLock('session_cleanup_daemon.lock')
        try:
            with lock.acquire(timeout=1):
                while True:
                    cleanup()
                    time.sleep(60 * 60 * 24)
        except filelock.Timeout:
            logger().info('only 1 process allowed at a time - lock file already held')
        except Exception:
            logger().exception('cleanup loop stopped unexpectedly')
            raise
    else:
        cleanup()
