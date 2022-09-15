import datetime
import logging
import logging.handlers
import sys
import time
import uuid

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.signals import setting_changed
from django.db import transaction
from django.db.models.functions import Now
from django.dispatch import receiver
from django.utils import timezone

from api import feed_handler, rss_requests
from api.models import Feed, FeedEntry

_SUCCESS_BACKOFF_SECONDS: int
_MIN_ERROR_BACKOFF_SECONDS: int
_MAX_ERROR_BACKOFF_SECONDS: int


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _SUCCESS_BACKOFF_SECONDS
    global _MIN_ERROR_BACKOFF_SECONDS
    global _MAX_ERROR_BACKOFF_SECONDS

    _SUCCESS_BACKOFF_SECONDS = settings.SUCCESS_BACKOFF_SECONDS
    _MIN_ERROR_BACKOFF_SECONDS = settings.MIN_ERROR_BACKOFF_SECONDS
    _MAX_ERROR_BACKOFF_SECONDS = settings.MAX_ERROR_BACKOFF_SECONDS


_load_global_settings()


_logger = logging.getLogger("rss_temple")


def scrape_feed(feed: Feed, response_text: str):
    d = feed_handler.text_2_d(response_text)

    new_feed_entries: list[FeedEntry] = []

    for d_entry in d.get("entries", []):
        feed_entry: FeedEntry
        try:
            feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
        except ValueError:  # pragma: no cover
            continue

        old_feed_entry: FeedEntry | None = None
        old_feed_entry_get_kwargs = {
            "feed": feed,
            "url": feed_entry.url,
        }
        if feed_entry.updated_at is None:
            old_feed_entry_get_kwargs["updated_at__isnull"] = True
        else:
            old_feed_entry_get_kwargs["updated_at"] = feed_entry.updated_at

        try:
            old_feed_entry = FeedEntry.objects.get(**old_feed_entry_get_kwargs)
        except FeedEntry.DoesNotExist:
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

    FeedEntry.objects.bulk_create(new_feed_entries)

    feed.db_updated_at = timezone.now()


def success_update_backoff_until(feed: Feed):
    return feed.db_updated_at + datetime.timedelta(seconds=_SUCCESS_BACKOFF_SECONDS)


def error_update_backoff_until(feed: Feed):
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


class Command(BaseCommand):
    help = "Scrape Feeds every 30 seconds"

    def add_arguments(self, parser):
        parser.add_argument("-c", "--count", type=int, default=1000)
        parser.add_argument("--feed-url")
        parser.add_argument("--feed-uuid")

    def handle(self, *args, **options):
        if options["feed_url"]:
            feed = Feed.objects.get(feed_url=options["feed_url"])

            response = rss_requests.get(feed.feed_url)
            response.raise_for_status()

            scrape_feed(feed, response.text)
        elif options["feed_uuid"]:
            feed = Feed.objects.get(uuid=uuid.UUID(options["feed_uuid"]))

            response = rss_requests.get(feed.feed_url)
            response.raise_for_status()

            scrape_feed(feed, response.text)
        else:
            try:
                while True:
                    count = 0
                    with transaction.atomic():
                        for feed in (
                            Feed.objects.select_for_update(skip_locked=True)
                            .filter(update_backoff_until__lte=Now())
                            .order_by("update_backoff_until")[: options["count"]]
                        ):
                            count += 1

                            try:
                                response = rss_requests.get(feed.feed_url)
                                response.raise_for_status()

                                scrape_feed(feed, response.text)

                                _logger.debug("scrapped '%s'", feed.feed_url)

                                feed.update_backoff_until = (
                                    success_update_backoff_until(feed)
                                )
                                feed.save(
                                    update_fields=[
                                        "db_updated_at",
                                        "update_backoff_until",
                                    ]
                                )
                            except requests.exceptions.RequestException:
                                _logger.exception(
                                    "failed to scrap feed '%s'", feed.feed_url
                                )

                                feed.update_backoff_until = error_update_backoff_until(
                                    feed
                                )
                                feed.save(update_fields=["update_backoff_until"])

                    _logger.info("scrapped %d feeds this round", count)

                    time.sleep(30)
            except Exception:
                _logger.exception("loop stopped unexpectedly")
                raise
