import datetime
import logging
import sys

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver

from api import feed_handler, models

_SUCCESS_BACKOFF_SECONDS = None
_MIN_ERROR_BACKOFF_SECONDS = None
_MAX_ERROR_BACKOFF_SECONDS = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _SUCCESS_BACKOFF_SECONDS
    global _MIN_ERROR_BACKOFF_SECONDS
    global _MAX_ERROR_BACKOFF_SECONDS

    _SUCCESS_BACKOFF_SECONDS = settings.SUCCESS_BACKOFF_SECONDS
    _MIN_ERROR_BACKOFF_SECONDS = settings.MIN_ERROR_BACKOFF_SECONDS
    _MAX_ERROR_BACKOFF_SECONDS = settings.MAX_ERROR_BACKOFF_SECONDS


_load_global_settings()


_logger = None


def logger():  # pragma: no cover
    global _logger

    if _logger is None:
        _logger = logging.getLogger("feed_scrapper_daemon")
        _logger.setLevel(logging.DEBUG)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s (%(levelname)s): %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        _logger.addHandler(stream_handler)

        file_handler = logging.handlers.RotatingFileHandler(
            filename="feed_scrapper_daemon.log", maxBytes=(50 * 100000), backupCount=3
        )
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s (%(levelname)s): %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        _logger.addHandler(file_handler)

    return _logger


def scrape_feed(feed, response_text):
    d = feed_handler.text_2_d(response_text)

    new_feed_entries = []

    for d_entry in d.get("entries", []):
        feed_entry = None
        try:
            feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
        except ValueError:  # pragma: no cover
            continue

        old_feed_entry = None
        old_feed_entry_get_kwargs = {
            "feed": feed,
            "url": feed_entry.url,
        }
        if feed_entry.updated_at is None:
            old_feed_entry_get_kwargs["updated_at__isnull"] = True
        else:
            old_feed_entry_get_kwargs["updated_at"] = feed_entry.updated_at

        try:
            old_feed_entry = models.FeedEntry.objects.get(**old_feed_entry_get_kwargs)
        except models.FeedEntry.DoesNotExist:
            pass

        if old_feed_entry is not None:
            old_feed_entry.id = feed_entry.id
            old_feed_entry.content = feed_entry.content
            old_feed_entry.author_name = feed_entry.author_name
            old_feed_entry.created_at = feed_entry.created_at
            old_feed_entry.updated_at = feed_entry.updated_at

            old_feed_entry.save(
                update_fields=[
                    "id",
                    "content",
                    "author_name",
                    "created_at",
                    "updated_at",
                ]
            )
        else:
            feed_entry.feed = feed
            new_feed_entries.append(feed_entry)

    models.FeedEntry.objects.bulk_create(new_feed_entries)

    feed.db_updated_at = datetime.datetime.now(datetime.timezone.utc)


def success_update_backoff_until(feed):
    return feed.db_updated_at + datetime.timedelta(seconds=_SUCCESS_BACKOFF_SECONDS)


def error_update_backoff_until(feed):
    last_written_at = feed.db_updated_at or feed.db_created_at

    backoff_delta_seconds = (
        feed.update_backoff_until - last_written_at
    ).total_seconds()

    if backoff_delta_seconds < _MIN_ERROR_BACKOFF_SECONDS:
        backoff_delta_seconds = _MIN_ERROR_BACKOFF_SECONDS
    elif backoff_delta_seconds > _MAX_ERROR_BACKOFF_SECONDS:
        backoff_delta_seconds += _MAX_ERROR_BACKOFF_SECONDS
    else:
        backoff_delta_seconds *= 2

    return last_written_at + datetime.timedelta(seconds=backoff_delta_seconds)
