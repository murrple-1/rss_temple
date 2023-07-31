import datetime
import time
from typing import Any, cast

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models.functions import Now
from django.db.utils import OperationalError
from django.utils import timezone

from api.models import Feed, FeedEntry, ReadFeedEntryUserMapping


class Command(BaseCommand):
    help = "Daemon to periodically mark old feed entries as archived"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-c", "--count", type=int, default=1000)
        parser.add_argument(
            "--sleep-seconds", type=float, default=60.0 * 30.0
        )  # 30 minutes
        parser.add_argument("--single-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["single_run"]:
            count = 0
            with transaction.atomic():
                for feed in (
                    Feed.objects.filter(archive_update_backoff_until__lte=Now())
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

            self.stderr.write(self.style.NOTICE(f"updated {count} feed archives"))
        else:
            try:
                while True:
                    count = 0
                    with transaction.atomic():
                        for feed in Feed.objects.filter(
                            archive_update_backoff_until__lte=Now()
                        ).order_by("archive_update_backoff_until")[
                            : cast(int, options["count"])
                        ]:
                            count += 1

                            self._handle_feed(
                                feed,
                                timezone.now(),
                                settings.ARCHIVE_TIME_THRESHOLD,
                                settings.ARCHIVE_COUNT_THRESHOLD,
                                settings.ARCHIVE_BACKOFF_SECONDS,
                            )

                    self.stderr.write(
                        self.style.NOTICE(f"updated {count} feed archives this round")
                    )

                    time.sleep(options["sleep_seconds"])
            except OperationalError as e:
                raise CommandError("db went away") from e
            except Exception as e:
                raise CommandError("loop stopped unexpectedly") from e

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
        newly_archived: list[FeedEntry] = []
        for feed_entry in feed.feed_entries.filter(is_archived=False).order_by(
            "-published_at", "-created_at", "-updated_at"
        ):
            count += 1
            if (
                feed_entry.published_at < time_cutoff
                or count >= archive_count_threshold
            ):
                feed_entry.is_archived = True
                newly_archived.append(feed_entry)

        FeedEntry.objects.bulk_update(newly_archived, ["is_archived"])

        ReadFeedEntryUserMapping.objects.filter(feed_entry__in=newly_archived).delete()

        feed.archive_update_backoff_until = now + datetime.timedelta(
            seconds=backoff_seconds
        )
        feed.save(
            update_fields=[
                "archive_update_backoff_until",
            ]
        )
