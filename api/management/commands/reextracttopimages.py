import datetime
import traceback
from typing import Any, Iterable

from django.core.management.base import CommandError, CommandParser
from django.db.utils import OperationalError
from django.utils import timezone

from api.models import FeedEntry
from api.top_image_extractor import extract_top_image_src, is_top_image_needed

from ._daemoncommand import DaemonCommand


class Command(DaemonCommand):
    help = "Daemon to find so-called 'top images' for entries without images"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--sleep-seconds", type=float, default=30.0)  # 30 seconds
        parser.add_argument("--single-run", action="store_true")
        parser.add_argument("--since")
        parser.add_argument("--loop-count", type=int, default=50)
        parser.add_argument("--image-min-bytes", type=int, default=20000)

    def handle(self, *args: Any, **options: Any) -> None:
        verbosity = options["verbosity"]
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
                    )
                    if verbosity >= 2:
                        self.stderr.write(self.style.NOTICE(f"updated {count}"))

                    exit.wait(options["sleep_seconds"])
            except OperationalError as e:
                raise CommandError("db went away") from e
            except Exception as e:
                raise CommandError("loop stopped unexpectedly") from e

    def _find_top_images(
        self,
        feed_entry_queryset: Iterable[FeedEntry],
    ) -> int:
        count = 0
        for feed_entry in feed_entry_queryset:
            try:
                if is_top_image_needed(feed_entry.content):
                    feed_entry.top_image_src = (
                        extract_top_image_src(feed_entry.url) or ""
                    )
                else:
                    feed_entry.top_image_src = ""

                feed_entry.has_top_image_been_processed = True
                feed_entry.save(
                    update_fields=("has_top_image_been_processed", "top_image_src")
                )

                count += 1
            except Exception:
                self.stderr.write(
                    self.style.ERROR(
                        f"failed to scrap feed '{feed_entry.url}'\n{traceback.format_exc()}"
                    )
                )
        return count
