import datetime
import traceback
from typing import Any, Iterable

from django.core.management.base import CommandError, CommandParser
from django.db.models import F
from django.db.utils import OperationalError
from django.utils import timezone

from api.models import FeedEntry
from api.top_image_extractor import TryAgain, extract_top_image_src, is_top_image_needed

from ._daemoncommand import DaemonCommand


class Command(DaemonCommand):
    help = "Daemon to find so-called 'top images' for entries without images"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("--sleep-seconds", type=float, default=30.0)  # 30 seconds
        parser.add_argument("--single-run", action="store_true")
        parser.add_argument("--since")
        parser.add_argument("--loop-count", type=int, default=50)
        parser.add_argument("--image-min-bytes", type=int, default=20000)
        parser.add_argument("--max-processing-attempts", type=int, default=3)
        parser.add_argument("--min-image-byte-count", type=int, default=4500)
        parser.add_argument("--min-image-width", type=int, default=256)
        parser.add_argument("--min-image-height", type=int, default=256)

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        verbosity = options["verbosity"]
        max_processing_attempts = options["max_processing_attempts"]
        min_image_byte_count = options["min_image_byte_count"]
        min_image_width = options["min_image_width"]
        min_image_height = options["min_image_height"]

        since = (
            datetime.datetime.fromisoformat(since_str)
            if (since_str := options["since"]) is not None
            else datetime.datetime.min
        )
        if timezone.is_naive(since):
            since = timezone.make_aware(since)

        if options["single_run"]:
            total_remaining = FeedEntry.objects.filter(
                has_top_image_been_processed=False
            ).count()

            count = self._find_top_images(
                FeedEntry.objects.filter(has_top_image_been_processed=False)
                .filter(published_at__gte=since)
                .order_by("-published_at")
                .iterator(),
                max_processing_attempts,
                min_image_byte_count,
                min_image_width,
                min_image_height,
                verbosity=verbosity,
            )
            self.stderr.write(f"updated {count}/{total_remaining}")
        else:
            exit = self._setup_exit_event()

            try:
                while not exit.is_set():
                    count = self._find_top_images(
                        FeedEntry.objects.filter(has_top_image_been_processed=False)
                        .filter(published_at__gte=since)
                        .order_by("-published_at")[: options["loop_count"]],
                        max_processing_attempts,
                        min_image_byte_count,
                        min_image_width,
                        min_image_height,
                        verbosity=verbosity,
                    )
                    self.stderr.write(self.style.NOTICE(f"updated {count}"))

                    exit.wait(options["sleep_seconds"])
            except OperationalError as e:
                raise CommandError("db went away") from e
            except Exception as e:
                raise CommandError("loop stopped unexpectedly") from e

    def _find_top_images(
        self,
        feed_entry_queryset: Iterable[FeedEntry],
        max_processing_attempts: int,
        min_image_byte_count: int,
        min_image_width: int,
        min_image_height: int,
        verbosity=1,
    ) -> int:
        count = 0
        for feed_entry in feed_entry_queryset:
            try:
                if is_top_image_needed(feed_entry.content):
                    feed_entry.top_image_src = (
                        extract_top_image_src(
                            feed_entry.url,
                            min_image_byte_count=min_image_byte_count,
                            min_image_width=min_image_width,
                            min_image_height=min_image_height,
                        )
                        or ""
                    )
                else:
                    feed_entry.top_image_src = ""

                feed_entry.has_top_image_been_processed = True
                feed_entry.save(
                    update_fields=("has_top_image_been_processed", "top_image_src")
                )

                count += 1
            except TryAgain:  # pragma: no cover
                if (
                    feed_entry.top_image_processing_attempt_count
                    < max_processing_attempts
                ):
                    FeedEntry.objects.filter(uuid=feed_entry.uuid).update(
                        top_image_processing_attempt_count=F(
                            "top_image_processing_attempt_count"
                        )
                        + 1
                    )
                    if verbosity >= 2:
                        self.stderr.write(
                            self.style.WARNING(
                                f"feed entry '{feed_entry.url}' transient error. try again later\n{traceback.format_exc()}"
                            )
                        )
                else:
                    FeedEntry.objects.filter(uuid=feed_entry.uuid).update(
                        top_image_src="", has_top_image_been_processed=True
                    )
                    count += 1

                    if verbosity >= 2:
                        self.stderr.write(
                            self.style.WARNING(
                                f"feed entry '{feed_entry.url}' transient error. no more attempts\n{traceback.format_exc()}"
                            )
                        )
            except Exception:  # pragma: no cover
                self.stderr.write(
                    self.style.ERROR(
                        f"failed to find top image for '{feed_entry.url}'\n{traceback.format_exc()}"
                    )
                )
        return count
