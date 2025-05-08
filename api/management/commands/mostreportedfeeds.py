from typing import Any
from collections import Counter

from django.core.management.base import BaseCommand, CommandParser
from tabulate import tabulate

from api.models import FeedReport, FeedEntryReport


class Command(BaseCommand):
    help = "Print the most reported feeds"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("--top", type=int, default=10)

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        counter: Counter[tuple[str, str]] = Counter()

        counter.update(FeedReport.objects.values_list("feed__title", "feed__feed_url"))
        counter.update(
            FeedEntryReport.objects.values_list(
                "feed_entry__feed__title", "feed_entry__feed__feed_url"
            )
        )

        self.stdout.write(
            tabulate(
                (
                    (count, title, feed_url)
                    for (title, feed_url), count in counter.most_common(options["top"])
                ),
                headers=[
                    "Count",
                    "Title",
                    "Feed URL",
                ],
            )
        )
