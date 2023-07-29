import datetime
import time
import traceback
from typing import Any, cast

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models.functions import Now
from django.utils import timezone

from api.models import Feed


class Command(BaseCommand):
    help = "Daemon to periodically mark old feed entries as archived"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-c", "--count", type=int, default=1000)
        parser.add_argument("--sleep-seconds", type=float, default=30.0)
        parser.add_argument("--single-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["single_run"]:
            count = 0
            with transaction.atomic():
                for feed in (
                    Feed.objects.select_for_update(skip_locked=True)
                    .filter(archive_update_backoff_until__lte=Now())
                    .order_by("archive_update_backoff_until")
                    .iterator()
                ):
                    count += 1

                    self._handle_feed(
                        feed,
                        timezone.now(),
                        settings.ARCHIVE_TIME_THRESHOLD,
                        settings.ARCHIVE_COUNT_THRESHOLD,
                        settings.ARCHIVE_BACKOFF_SECONDS,
                    )

            self.stderr.write(self.style.NOTICE(f"scrapped {count} feeds"))
        else:
            try:
                while True:
                    count = 0
                    with transaction.atomic():
                        for feed in (
                            Feed.objects.select_for_update(skip_locked=True)
                            .filter(archive_update_backoff_until__lte=Now())
                            .order_by("archive_update_backoff_until")[
                                : cast(int, options["count"])
                            ]
                        ):
                            count += 1

                            self._handle_feed(
                                feed,
                                timezone.now(),
                                settings.ARCHIVE_TIME_THRESHOLD,
                                settings.ARCHIVE_COUNT_THRESHOLD,
                                settings.ARCHIVE_BACKOFF_SECONDS,
                            )

                    self.stderr.write(
                        self.style.NOTICE(f"scrapped {count} feeds this round")
                    )

                    time.sleep(options["sleep_seconds"])
            except Exception:
                self.stderr.write(
                    self.style.ERROR(
                        f"loop stopped unexpectedly\n{traceback.format_exc()}"
                    )
                )
                raise

    def _handle_feed(
        self,
        feed: Feed,
        now: datetime.datetime,
        archive_time_threshold: datetime.timedelta,
        archive_count_threshold: int,
        backoff_seconds: float,
    ) -> None:
        time_cutoff = now + archive_time_threshold

        count = 0
        for feed_entry in feed.feed_entries.filter(is_archived=False).order_by(
            "-published_at", "-created_at", "-updated_at"
        ):
            count += 1
            if (
                feed_entry.published_at < time_cutoff
                or count >= archive_count_threshold
            ):
                feed_entry.is_archived = True
                feed_entry.save(
                    update_fields=[
                        "is_archived",
                    ]
                )
                feed_entry.read_user_set.clear()

        feed.archive_update_backoff_until = now + datetime.timedelta(
            seconds=backoff_seconds
        )
        feed.save(
            update_fields=[
                "archive_update_backoff_until",
            ]
        )
