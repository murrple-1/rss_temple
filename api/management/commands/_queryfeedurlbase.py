import traceback
from typing import Any, Iterable

from django.core.management.base import BaseCommand as BaseCommand_
from django.db import IntegrityError, transaction
from django.utils import timezone
from tabulate import tabulate

from api import feed_handler, rss_requests
from api.models import Feed, FeedEntry
from api.tasks.feed_scrape import feed_scrape
from api.text_classifier.lang_detector import detect_iso639_3
from api.text_classifier.prep_content import prep_for_lang_detection


class BaseCommand(BaseCommand_):
    def _query_feed_url(
        self,
        normalized_feed_urls: Iterable[str],
        save=False,
        print_feed=False,
        print_entries=False,
        with_content=False,
        max_db_feed_entries=20,
    ):
        now = timezone.now()

        feeds: list[Feed] = []
        new_feeds: list[Feed] = []
        feed_entries: list[FeedEntry] = []
        new_feed_entries: list[FeedEntry] = []
        for feed_url in normalized_feed_urls:
            try:
                feed = Feed.objects.prefetch_related("feed_entries").get(
                    feed_url=feed_url
                )
                feeds.append(feed)

                if save:
                    response = rss_requests.get(feed_url)
                    response.raise_for_status()
                    try:
                        with transaction.atomic():
                            feed_scrape(feed, response.text)
                            feed.save(update_fields=["db_updated_at"])
                    except IntegrityError:
                        self.stderr.write(
                            self.style.ERROR(
                                f"unable to scape feed '{feed_url}'\n{traceback.format_exc()}"
                            )
                        )

                feed_entries.extend(
                    feed.feed_entries.select_related("feed").order_by("-published_at")[
                        :max_db_feed_entries
                    ]
                )
            except Feed.DoesNotExist:
                response = rss_requests.get(feed_url)
                response.raise_for_status()

                d = feed_handler.text_2_d(response.text)

                feed = feed_handler.d_feed_2_feed(d.feed, feed_url, now)
                feeds.append(feed)
                new_feeds.append(feed)

                for index, d_entry in enumerate(d.get("entries", [])):
                    feed_entry: FeedEntry
                    try:
                        feed_entry = feed_handler.d_entry_2_feed_entry(d_entry, now)
                    except ValueError:  # pragma: no cover
                        self.stderr.write(
                            self.style.ERROR(
                                f"unable to parse d_entry {index}\n{traceback.format_exc()}"
                            )
                        )
                        continue

                    feed_entry.feed = feed

                    feed_entry.language_id = detect_iso639_3(
                        prep_for_lang_detection(feed_entry.title, feed_entry.content)
                    )

                    feed_entries.append(feed_entry)
                    new_feed_entries.append(feed_entry)

        if save and new_feeds:
            with transaction.atomic():
                for feed in new_feeds:
                    feed.with_subscription_data()
                    feed.save()

                FeedEntry.objects.bulk_create(new_feed_entries)

        table: list[list[Any]]
        if print_feed:
            self.stdout.write(
                tabulate(
                    (
                        (
                            feed.uuid,
                            feed.feed_url,
                            feed.title,
                            feed.home_url,
                            feed.published_at,
                            feed.updated_at,
                        )
                        for feed in feeds
                    ),
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

        if print_entries:
            table = []
            for feed_entry in feed_entries:
                row = [
                    feed_entry.uuid,
                    feed_entry.feed.feed_url,
                    feed_entry.id,
                    feed_entry.created_at,
                    feed_entry.updated_at,
                    feed_entry.title,
                    feed_entry.url,
                    feed_entry.author_name,
                ]
                if with_content:
                    row.append(feed_entry.content)
                row.append(feed_entry.language_id)

                table.append(row)

            headers = [
                "UUID",
                "Feed URL",
                "ID",
                "Created At",
                "Updated At",
                "Title",
                "URL",
                "Author Name",
            ]
            if with_content:
                headers.append("Content")
            headers.append("Language")

            self.stdout.write(
                tabulate(
                    table,
                    headers=headers,
                )
            )
