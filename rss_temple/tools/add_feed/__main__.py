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

import argparse
import sys

import requests

from api import models, rss_requests, feed_handler

_logger = None


def logger():  # pragma: no cover
    global _logger
    if _logger is None:
        _logger = logging.getLogger(__name__)

    return _logger

# monkey-patch the feed_handler logging
feed_handler.logger = logger

parser = argparse.ArgumentParser()
parser.add_argument('feed_url')
parser.add_argument('-d', '--dry-run', action='store_true')
args = parser.parse_args()

if models.Feed.objects.filter(feed_url=args.feed_url).exists():
    logger().error('feed already exists')
    sys.exit(-1)

response = None
try:
    response = rss_requests.get(args.feed_url)
    response.raise_for_status()
except requests.exceptions.RequestException:
    logger().exception('failed to scrap feed \'%s\'', args.feed_url)
    sys.exit(-2)

d = feed_handler.text_2_d(response.text)

if not args.dry_run:
    feed = feed_handler.d_feed_2_feed(d.feed, args.feed_url)
    feed.with_subscription_data()
    feed.save()

    feed_entries = []

    for d_entry in d.get('entries', []):
        feed_entry = None
        try:
            feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
        except ValueError:  # pragma: no cover
            continue

        feed_entry.feed = feed

        feed_entries.append(feed_entry)

    models.FeedEntry.objects.bulk_create(feed_entries)
