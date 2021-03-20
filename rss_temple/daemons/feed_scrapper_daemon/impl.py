import logging
import sys

from django.db.models.functions import Now

from api import feed_handler, models


_logger = None


def logger():  # pragma: no cover
    global _logger

    if _logger is None:
        _logger = logging.getLogger('feed_scapper_daemon')
        _logger.setLevel(logging.DEBUG)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(stream_handler)

        file_handler = logging.handlers.RotatingFileHandler(
            filename='feed_scrapper_daemon.log', maxBytes=(
                50 * 100000), backupCount=3)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(file_handler)

    return _logger


def scrape_feed(feed, response_text):
    d = feed_handler.text_2_d(response_text)

    feed_entries = []

    for d_entry in d.get('entries', []):
        feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
        feed_entry.feed = feed

        if models.FeedEntry.objects.filter(feed=feed, hash=feed_entry.hash).exists():
            continue

        feed_entries.append(feed_entry)

    models.FeedEntry.objects.bulk_create(feed_entries)

    feed.db_updated_at = Now()
    feed.save()
