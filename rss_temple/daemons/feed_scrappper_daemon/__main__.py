# Setting up Django

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rss_temple.settings')

# django.conf.settings requires these be set, but the value doesn't matter
# for this script
os.environ.setdefault('SECRET_KEY', '<SECRET_KEY>')

import django

django.setup()

import time
import argparse
import logging

from django.db import transaction

import filelock

from . import logger, scrape_feed
from api import models

def _scrape_loop():
    feeds = models.Feed.objects.select_for_update(skip_locked=True).all()
    with transaction.atomic():
        for feed in feeds:
            scrape_feed(feed)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--feed-url')
    parser.add_argument('--feed-uuid')
    args = parser.parse_args()

    logger().setLevel(logging.DEBUG)

    if not args.force_now:
        lock = filelock.FileLock('feed_scapper_daemon.lock')
        try:
            with lock.acquire(timeout=1):
                while True:
                    _scrape_loop()
                    time.sleep(60 * 60 * 24)
        except filelock.Timeout:
            logger().info('only 1 process allowed at a time - lock file already held')
        except Exception:
            logger().exception('loop stopped unexpectedly')
            raise
    else:
        # TODO
        pass


if __name__ == '__main__':
    main()
