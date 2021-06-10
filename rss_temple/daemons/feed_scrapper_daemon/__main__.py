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
from django.db.models.functions import Now

import filelock

import requests

from .impl import logger, scrape_feed, success_update_backoff_until, error_update_backoff_until
from api import models, rss_requests
from api.exceptions import QueryException


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
    lock = filelock.FileLock('feed_scrapper_daemon.lock')
    try:
        with lock.acquire(timeout=1):
            while True:
                count = 0
                with transaction.atomic():
                    for feed in models.Feed.objects.select_for_update(skip_locked=True).filter(update_backoff_until__lte=Now()).order_by('update_backoff_until')[:args.count]:
                        count += 1

                        try:
                            response = rss_requests.get(feed.feed_url)
                            response.raise_for_status()

                            scrape_feed(feed, response.text)

                            logger().debug('scrapped \'%s\'', feed.feed_url)

                            feed.update_backoff_until = success_update_backoff_until(
                                feed)
                            feed.save(update_fields=[
                                      'db_updated_at', 'update_backoff_until'])
                        except (requests.exceptions.RequestException, QueryException):
                            logger().exception('failed to scrap feed \'%s\'', feed.feed_url)

                            feed.update_backoff_until = error_update_backoff_until(
                                feed)
                            feed.save(update_fields=['update_backoff_until'])

                logger().info('scrapped %d feeds this round', count)

                time.sleep(30)
    except filelock.Timeout:
        logger().info('only 1 process allowed at a time - lock file already held')
    except Exception:
        logger().exception('loop stopped unexpectedly')
        raise
