import traceback
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from tabulate import tabulate

from api import feed_handler, rss_requests
from api.models import FeedEntry, FeedEntryLanguageMapping
from api.text_classifier.lang_detector import detect_thresholded_iso639_3s
from api.text_classifier.prep_content import prep_for_lang_detection


class Command(BaseCommand):
    help = "Tool to query real RSS feeds, and potentially force them into the DB"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("feed_url")
        parser.add_argument("-s", "--save", action="store_true")
        parser.add_argument("-f", "--print-feed", action="store_true")
        parser.add_argument("-e", "--print-entries", action="store_true")
        parser.add_argument("-c", "--with-content", action="store_true")
        parser.add_argument(
            "--lingua-confidence-threshold",
            type=float,
            default=settings.LINGUA_CONFIDENCE_THRESHOLD,
        )

    def handle(self, *args: Any, **options: Any):
        response = rss_requests.get(options["feed_url"])
        response.raise_for_status()

        d = feed_handler.text_2_d(response.text)

        feed = feed_handler.d_feed_2_feed(d.feed, options["feed_url"])

        feed_entries: list[FeedEntry] = []

        for index, d_entry in enumerate(d.get("entries", [])):
            feed_entry: FeedEntry
            try:
                feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
            except ValueError:  # pragma: no cover
                self.stderr.write(
                    self.style.ERROR(
                        f"unable to parse d_entry {index}\n{traceback.format_exc()}"
                    )
                )
                continue

            feed_entry.feed = feed

            feed_entries.append(feed_entry)

        table: list[list[Any]]
        if options["print_feed"]:
            table = [
                [
                    feed.uuid,
                    feed.feed_url,
                    feed.title,
                    feed.home_url,
                    feed.published_at,
                    feed.updated_at,
                ],
            ]
            self.stdout.write(
                tabulate(
                    table,
                    headers=[
                        "UUID",
                        "Feed URL",
                        "Title",
                        "Home URL",
                        "Published At",
                        "Updated At",
                    ],
                )
            )

        if options["print_entries"]:
            table = []
            for feed_entry in feed_entries:
                row = [
                    feed_entry.uuid,
                    feed_entry.id,
                    feed_entry.created_at,
                    feed_entry.updated_at,
                    feed_entry.title,
                    feed_entry.url,
                    feed_entry.author_name,
                ]
                if options["with_content"]:
                    row.append(feed_entry.content)

                table.append(row)

            headers = [
                "UUID",
                "ID",
                "Created At",
                "Updated At",
                "Title",
                "URL",
                "Author Name",
            ]

            if options["with_content"]:
                headers.append("Content")

            self.stdout.write(
                tabulate(
                    table,
                    headers=headers,
                )
            )

        if options["save"]:
            feed.with_subscription_data()

            with transaction.atomic():
                feed.save()

                FeedEntry.objects.bulk_create(feed_entries)

                for feed_entry in feed_entries:
                    content = prep_for_lang_detection(feed_entry.content)
                    detected_languages = detect_thresholded_iso639_3s(
                        content, options["lingua_confidence_threshold"]
                    )
                    FeedEntryLanguageMapping.objects.bulk_create(
                        FeedEntryLanguageMapping(
                            language_id=lang,
                            feed_entry=feed_entry,
                            confidence=confidence,
                        )
                        for lang, confidence in detected_languages.items()
                    )
