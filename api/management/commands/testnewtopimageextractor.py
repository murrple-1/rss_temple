from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import FeedEntry
from api.top_image_extractor import extract_top_image_src__experimental


class Command(BaseCommand):
    help = "Test the old and new top image extraction"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--count", type=int, default=10)
        parser.add_argument("--min-image-byte-count", type=int, default=4500)
        parser.add_argument("--min-image-width", type=int, default=256)
        parser.add_argument("--min-image-height", type=int, default=256)
        parser.add_argument("--response-max-byte-count", type=int, default=-1)

    def handle(self, *args: Any, **options: Any) -> None:
        for feed_entry in FeedEntry.objects.filter(
            has_top_image_been_processed=True
        ).order_by("?")[: options["count"]]:
            try:
                img_srcs = extract_top_image_src__experimental(
                    feed_entry.url,
                    options["response_max_byte_count"],
                    min_image_byte_count=options["min_image_byte_count"],
                    min_image_width=options["min_image_width"],
                    min_image_height=options["min_image_height"],
                )

                img_srcs_str = "\n".join(img_srcs) if img_srcs is not None else None
                if (not feed_entry.top_image_src and img_srcs) or (
                    feed_entry.top_image_src
                    and (not img_srcs or img_srcs[0] != feed_entry.top_image_src)
                ):
                    self.stderr.write(
                        self.style.NOTICE(
                            f"different result for {feed_entry.url}\n\n{feed_entry.top_image_src=}\n\nimg_srcs_str={img_srcs_str}"
                        )
                    )
                else:
                    self.stderr.write(
                        self.style.NOTICE(
                            f"same result for {feed_entry.url}\n\n{feed_entry.top_image_src=}\n\nimg_srcs_str={img_srcs_str}"
                        )
                    )
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"failed for {feed_entry.url}: {e}"))
