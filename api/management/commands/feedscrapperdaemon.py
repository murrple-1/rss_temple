import datetime
import time
import traceback
import uuid
from typing import Any

import filelock
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.core.signals import setting_changed
from django.db import transaction
from django.db.models.functions import Now
from django.dispatch import receiver
from django.utils import timezone

from api import feed_handler, models, rss_requests
from api.exceptions import QueryException


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _SUCCESS_BACKOFF_SECONDS
    global _MIN_ERROR_BACKOFF_SECONDS
    global _MAX_ERROR_BACKOFF_SECONDS

    _SUCCESS_BACKOFF_SECONDS = settings.SUCCESS_BACKOFF_SECONDS
    _MIN_ERROR_BACKOFF_SECONDS = settings.MIN_ERROR_BACKOFF_SECONDS
    _MAX_ERROR_BACKOFF_SECONDS = settings.MAX_ERROR_BACKOFF_SECONDS


_load_global_settings()


class Command(BaseCommand):
    help = "Daemon to send periodically web-scrape the various feeds and update our DB"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-c", "--count", type=int, default=1000)
        parser.add_argument("--feed-url")
        parser.add_argument("--feed-uuid")

    def handle(self, *args: Any, **options: Any) -> str | None:
        if options["feed_url"] or options["feed_uuid"]:
            feed = None
            if options["feed_url"]:
                feed = models.Feed.objects.get(feed_url=options["feed_url"])
            elif options["feed_uuid"]:
                feed = models.Feed.objects.get(uuid=uuid.UUID(options["feed_uuid"]))
            else:
                raise RuntimeError

            response = rss_requests.get(feed.feed_url)
            response.raise_for_status()
            self._scrape_feed(feed, response.text)
        else:
            lock = filelock.FileLock("feed_scrapper_daemon.lock")
            try:
                with lock.acquire(timeout=1):
                    while True:
                        count = 0
                        with transaction.atomic():
                            for feed in (
                                models.Feed.objects.select_for_update(skip_locked=True)
                                .filter(update_backoff_until__lte=Now())
                                .order_by("update_backoff_until")[: args.count]
                            ):
                                count += 1

                                try:
                                    response = rss_requests.get(feed.feed_url)
                                    response.raise_for_status()

                                    self._scrape_feed(feed, response.text)

                                    self.stderr.write(
                                        self.style.NOTICE(f"scrapped '{feed.feed_url}'")
                                    )

                                    feed.update_backoff_until = (
                                        self._success_update_backoff_until(feed)
                                    )
                                    feed.save(
                                        update_fields=[
                                            "db_updated_at",
                                            "update_backoff_until",
                                        ]
                                    )
                                except (
                                    requests.exceptions.RequestException,
                                    QueryException,
                                ):
                                    self.stderr.write(
                                        self.style.ERROR(
                                            f"failed to scrap feed '{feed.feed_url}'\n{traceback.format_exc()}"
                                        )
                                    )

                                    feed.update_backoff_until = (
                                        self._error_update_backoff_until(feed)
                                    )
                                    feed.save(update_fields=["update_backoff_until"])

                        self.stderr.write(
                            self.style.NOTICE(f"scrapped {count} feeds this round")
                        )

                        time.sleep(30)
            except filelock.Timeout:
                self.stderr.write(
                    self.style.WARNING(
                        "only 1 process allowed at a time - lock file already held"
                    )
                )
            except Exception:
                self.stderr.write(
                    self.style.ERROR(
                        f"render loop stopped unexpectedly\n{traceback.format_exc()}"
                    )
                )
                raise

    def _scrape_feed(self, feed, response_text):
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
                old_feed_entry = models.FeedEntry.objects.get(
                    **old_feed_entry_get_kwargs
                )
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

        feed.db_updated_at = timezone.now()

    def _success_update_backoff_until(self, feed):
        return feed.db_updated_at + datetime.timedelta(seconds=_SUCCESS_BACKOFF_SECONDS)

    def _error_update_backoff_until(self, feed):
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
