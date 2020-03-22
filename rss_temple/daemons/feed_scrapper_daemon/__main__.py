# Setting up Django

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rss_temple.settings')

# django.conf.settings requires these be set, but the value doesn't matter
# for this script
os.environ.setdefault('SECRET_KEY', '<SECRET_KEY>')
os.environ.setdefault('GOOGLE_CLIENT_ID', '<GOOGLE_CLIENT_ID>')

import django

django.setup()

# regularly scheduled programming

import time
import argparse
import uuid

from django.db import transaction
from django.db.models import F

import filelock

import requests

from . import logger, scrape_feed
from api import models, rss_requests


parser = argparse.ArgumentParser()
parser.add_argument('-c', '--count', type=int, default=1000)
parser.add_argument('--feed-url')
parser.add_argument('--feed-uuid')
args = parser.parse_args()

if args.feed_url or args.feed_uuid:
    feed = None
    if args.feed_url:
        feed = models.Feed.objects.get(feed_url=args.feed_url)
    elif args.feed_uuid:
        feed = models.Feed.objects.get(uuid=uuid.UUID(args.feed_uuid))
    scrape_feed(feed)
else:
    lock = filelock.FileLock('feed_scapper_daemon.lock')
    try:
        with lock.acquire(timeout=1):
            while True:
                with transaction.atomic():
                    for feed in models.Feed.objects.select_for_update(skip_locked=True).order_by(F('db_updated_at').desc(nulls_first=True))[:args.count]:
                        response = None
                        try:
                            response = rss_requests.get(feed.feed_url)
                            response.raise_for_status()
                        except requests.exceptions.RequestException:
                            continue

                        scrape_feed(feed, response.text)

                time.sleep(30)
    except filelock.Timeout:
        logger().info('only 1 process allowed at a time - lock file already held')
    except Exception:
        logger().exception('loop stopped unexpectedly')
        raise
