from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import DuplicateFeedSuggestion
from api.tasks import find_duplicate_feeds


class Command(BaseCommand):
    help = "Heuristic-based algorithm to find feeds that are pointing at the same feed (just with different URLs), so they can be combined"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--feed-count", type=int, default=1000)
        parser.add_argument("--entry-compare-count", type=int, default=50)
        parser.add_argument("--entry-intersection-threshold", type=int, default=5)

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        duplicate_feed_suggestions: list[DuplicateFeedSuggestion] = []

        for f1, f2 in find_duplicate_feeds(
            options["feed_count"],
            options["entry_compare_count"],
            options["entry_intersection_threshold"],
        ):
            self.stderr.write(self.style.NOTICE(f"{f1.feed_url} : {f2.feed_url}"))

            f1_id, f2_id = sorted([f1.uuid, f2.uuid], reverse=True)
            duplicate_feed_suggestions.append(
                DuplicateFeedSuggestion(feed1_id=f1_id, feed2_id=f2_id)
            )

        DuplicateFeedSuggestion.objects.bulk_create(
            duplicate_feed_suggestions, ignore_conflicts=True
        )
