import csv
import json
import sys
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import ClassifierLabelFeedEntryVote, FeedEntry


class Command(BaseCommand):
    help = "Output a CSV of article entries with labels for machine learning"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--count", type=int, default=1000)
        parser.add_argument("--most-common-count", type=int, default=3)

    def handle(self, *args: Any, **options: Any) -> None:
        count = options["count"]
        most_common_count = options["most_common_count"]

        writer = csv.DictWriter(sys.stdout, fieldnames=("title", "content", "labels"))
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
            labels = counter.most_common(most_common_count)
            if not labels:
                continue

            writer.writerow(
                {
                    "title": feed_entry_dict["title"],
                    "content": feed_entry_dict["content"],
                    "labels": json.dumps([label[0] for label in labels]),
                }
            )
            output_count += 1
