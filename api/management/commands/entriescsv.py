import csv
import sys
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import ClassifierLabelFeedEntryVote, FeedEntry


class Command(BaseCommand):
    help = "Output a CSV of article entries with labels for machine learning"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--count", type=int, default=1000)

    def handle(self, *args: Any, **options: Any) -> None:
        count = options["count"]

        writer = csv.DictWriter(sys.stdout, fieldnames=("title", "content", "label"))
        writer.writeheader()

        output_count = 0
        for feed_entry_dict in (
            FeedEntry.objects.filter(
                language="ENG",
            )
            .order_by("?")
            .values("title", "content", "uuid")
        ).iterator():
            if output_count >= count:
                break

            counter = Counter(
                ClassifierLabelFeedEntryVote.objects.filter(
                    feed_entry_id=feed_entry_dict["uuid"]
                )
                .values_list("classifier_label__text", flat=True)
                .iterator()
            )
            labels = counter.most_common(1)
            if not labels:
                continue

            writer.writerow(
                {
                    "title": feed_entry_dict["title"],
                    "content": feed_entry_dict["content"],
                    "label": labels[0][0],
                }
            )
            output_count += 1
