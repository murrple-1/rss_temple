from typing import Any, Literal

from django.core.management.base import BaseCommand, CommandError, CommandParser

from api.content_sanitize import sanitize
from api.models import FeedEntry


class Command(BaseCommand):
    help = "Rerun sanitization of the feed entry content"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--sanitize-loop", dest="sanitize_loop_count", type=int, default=1
        )
        parser.add_argument(
            "--sanity-check",
            dest="sanity_check_type",
            choices=["none", "warn", "error"],
            default="none",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        verbosity = options["verbosity"]
        dry_run = options["dry_run"]
        sanitize_loop_count = options["sanitize_loop_count"]
        sanity_check_type = options["sanity_check_type"]

        total = FeedEntry.objects.count()

        update_count = 0
        overall_count = 0
        try:
            for overall_count, feed_entry in enumerate(
                FeedEntry.objects.order_by("-published_at").iterator()
            ):
                old_content = feed_entry.content
                new_content = old_content
                for _ in range(sanitize_loop_count):
                    new_content_ = new_content
                    new_content = sanitize(new_content)
                    if new_content == new_content_:
                        break
                if old_content != new_content:
                    if sanity_check_type in ("warn", "error"):
                        self._sanity_check(
                            feed_entry, old_content, new_content, sanity_check_type
                        )

                    feed_entry.content = new_content
                    if not dry_run:
                        feed_entry.save(update_fields=["content"])
                    update_count += 1

                    if verbosity >= 2:
                        self.stderr.write(
                            self.style.NOTICE(f"updated\t{overall_count + 1}/{total}")
                        )
                    if verbosity >= 3:
                        self.stderr.write(f"{old_content=}\n{new_content=}")
                else:
                    if verbosity >= 2:
                        self.stderr.write(
                            self.style.NOTICE(f"skip\t{overall_count + 1}/{total}")
                        )
        except KeyboardInterrupt:
            pass
        finally:
            if verbosity >= 1:
                self.stderr.write(
                    self.style.NOTICE(
                        f"updated {update_count}. checked {overall_count + 1}/{total} ({((overall_count + 1) / total) * 100.0}%)"
                    )
                )

    def _sanity_check(
        self,
        feed_entry: FeedEntry,
        old_content: str,
        new_content: str,
        check_style: Literal["warn"] | Literal["error"],
    ):
        new_new_content = sanitize(new_content)
        if new_content != new_new_content:
            warn_text = f"`sanitize()` is not consistent (Entry {feed_entry.uuid})\n{old_content=}\n{new_content=}\n{new_new_content=}"
            if check_style == "warn":
                self.stderr.write(self.style.WARNING(warn_text))
            elif check_style == "error":
                raise CommandError(warn_text)
            else:
                raise RuntimeError("unknown check_style")
