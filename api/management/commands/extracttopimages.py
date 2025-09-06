import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from api.models import FeedEntry
from api.tasks import extract_top_images


class Command(BaseCommand):
    help = "Find so-called 'top images' for entries without images"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("--since")
        parser.add_argument("--max-processing-attempts", type=int, default=3)
        parser.add_argument("--min-image-byte-count", type=int, default=4500)
        parser.add_argument("--min-image-width", type=int, default=256)
        parser.add_argument("--min-image-height", type=int, default=256)
        parser.add_argument("--response-max-byte-count", type=int, default=-1)
        parser.add_argument("--large-backlog-threshold", type=int, default=200)

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        since = (
            datetime.datetime.fromisoformat(since_str)
            if (since_str := options["since"]) is not None
            else datetime.datetime.min
        )
        if timezone.is_naive(since):
            since = timezone.make_aware(since)

        total_remaining = FeedEntry.objects.filter(
            has_top_image_been_processed=False
        ).count()

        self.stderr.write(
            self.style.NOTICE(f"{total_remaining} feed entries need processing")
        )

        large_backlog_threshold = options["large_backlog_threshold"]
        if total_remaining > large_backlog_threshold:
            self.stderr.write(
                self.style.WARNING(
                    f"large backlog alert: {total_remaining} is larger than threshold {large_backlog_threshold}"
                )
            )

        qs = FeedEntry.objects.filter(has_top_image_been_processed=False).filter(
            published_at__gte=since
        )

        self.stderr.write(self.style.NOTICE(f"handling {qs.count()} feed entries..."))

        try:
            count = extract_top_images(
                qs.order_by("-published_at").select_related("language").iterator(),
                options["max_processing_attempts"],
                options["min_image_byte_count"],
                options["min_image_width"],
                options["min_image_height"],
                options["response_max_byte_count"],
            )
            self.stderr.write(self.style.NOTICE(f"updated {count}/{total_remaining}"))
        except KeyboardInterrupt:
            pass
