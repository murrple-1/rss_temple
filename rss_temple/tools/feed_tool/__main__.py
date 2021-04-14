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
import logging
import sys

from django.db import transaction

from tabulate import tabulate

from api import models, rss_requests, feed_handler

_logger = None


def logger():  # pragma: no cover
    global _logger
    if _logger is None:
        _logger = logging.getLogger(__name__)
        _logger.setLevel(logging.DEBUG)

        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(stream_handler)

    return _logger

# monkey-patch the feed_handler logging
feed_handler.logger = logger

parser = argparse.ArgumentParser()
parser.add_argument('feed_url')
parser.add_argument('-s', '--save', action='store_true')
parser.add_argument('-f', '--print-feed', action='store_true')
parser.add_argument('-e', '--print-entries', action='store_true')
args = parser.parse_args()

response = rss_requests.get(args.feed_url)
response.raise_for_status()

d = feed_handler.text_2_d(response.text)

feed = feed_handler.d_feed_2_feed(d.feed, args.feed_url)

feed_entries = []

for index, d_entry in enumerate(d.get('entries', [])):
    feed_entry = None
    try:
        feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
    except ValueError:  # pragma: no cover
        logger().exception(f'unable to parse d_entry {index}')
        continue

    feed_entry.feed = feed

    feed_entries.append(feed_entry)

if args.print_feed:
    table = [
        [
            feed.uuid,
            feed.feed_url,
            feed.title,
            feed.home_url,
            feed.published_at,
            feed.updated_at,
        ],
    ]
    print(tabulate(table, headers=[
        'UUID',
        'Feed URL',
        'Title',
        'Home URL',
        'Published At',
        'Updated At',
    ]))

if args.print_entries:
    table = []
    for feed_entry in feed_entries:
        table.append([
            feed_entry.uuid,
            feed_entry.id,
            feed_entry.created_at,
            feed_entry.updated_at,
            feed_entry.title,
            feed_entry.url,
            feed_entry.content,
            feed_entry.author_name,
        ])

    print(tabulate(table, headers=[
        'UUID',
        'ID',
        'Created At',
        'Updated At',
        'Title',
        'URL',
        'Content',
        'Author Name',
    ]))

if args.save:
    feed.with_subscription_data()

    with transaction.atomic():
        feed.save()

        models.FeedEntry.objects.bulk_create(feed_entries)
