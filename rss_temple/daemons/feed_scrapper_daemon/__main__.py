import time
import argparse
import logging
import uuid

from django.db import transaction
from django.db.models import F

import filelock

from . import logger, scrape_feed
from api import models

def _scrape_loop(count):
    feeds = models.Feed.objects.select_for_update(skip_locked=True).order_by(F('db_updated_at').desc(nulls_first=True))[:count]
    with transaction.atomic():
        for feed in feeds:
            scrape_feed(feed)

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--count', type=int, default=1000)
parser.add_argument('--feed-url')
parser.add_argument('--feed-uuid')
args = parser.parse_args()

logger().setLevel(logging.DEBUG)

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
                _scrape_loop(args.count)
                time.sleep(30)
    except filelock.Timeout:
        logger().info('only 1 process allowed at a time - lock file already held')
    except Exception:
        logger().exception('loop stopped unexpectedly')
        raise
