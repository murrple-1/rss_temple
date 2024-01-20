import traceback
from typing import Any, Collection

from django.conf import settings
from django.core.management.base import BaseCommand as BaseCommand_
from django.db import IntegrityError, transaction
from django.utils import timezone
from requests.exceptions import RequestException
from tabulate import tabulate

from api import content_type_util, feed_handler, rss_requests
from api.content_type_util import WrongContentTypeError
from api.feed_handler import FeedHandlerError
from api.models import Feed, FeedEntry
from api.requests_extensions import ResponseTooBig, safe_response_text
from api.tasks.feed_scrape import feed_scrape
from api.text_classifier.lang_detector import detect_iso639_3
from api.text_classifier.prep_content import prep_for_lang_detection


class BaseCommand(BaseCommand_):
    def _query_feed_url(
        self,
        normalized_feed_urls: Collection[str],
        save=False,
        print_feeds=False,
        print_entries=False,
        with_content=False,
        max_db_feed_entries=20,
        verbosity=1,
    ):
        now = timezone.now()

        feeds: list[Feed] = []
        new_feeds: list[Feed] = []
        feed_entries: list[FeedEntry] = []
        new_feed_entries: list[FeedEntry] = []
        failed_feed_urls: list[str] = []
        response_text: str

        url_count = len(normalized_feed_urls)
        for i, feed_url in enumerate(normalized_feed_urls):
            if url_count > 1:
                self.stderr.write(
                    self.style.NOTICE(
                        f"querying feed {i + 1}/{url_count} ({feed_url})..."
                    )
                )

            try:
                feed = Feed.objects.prefetch_related("feed_entries").get(
                    feed_url=feed_url
                )
                feeds.append(feed)

                if save:
                    try:
                        with rss_requests.get(feed_url, stream=True) as response:
                            response.raise_for_status()
                            content_type = response.headers.get("Content-Type")
                            if (
                                content_type is not None
                                and not content_type_util.is_feed(content_type)
                            ):
                                raise WrongContentTypeError(content_type)

                            response_text = safe_response_text(
                                response,
                                settings.DOWNLOAD_MAX_BYTE_COUNT,
                            )
                    except (
                        RequestException,
                        ResponseTooBig,
                        WrongContentTypeError,
                    ):
                        if verbosity >= 2:
                            self.stderr.write(
                                self.style.ERROR(
                                    f"unable to load '{feed_url}'\n{traceback.format_exc()}"
                                )
                            )
                        failed_feed_urls.append(feed_url)
                        continue

                    try:
                        with transaction.atomic():
                            feed_scrape(feed, response_text)
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
                try:
                    with rss_requests.get(feed_url, stream=True) as response:
                        response.raise_for_status()
                        content_type = response.headers.get("Content-Type")
                        if content_type is not None and not content_type_util.is_feed(
                            content_type
                        ):
                            raise WrongContentTypeError(content_type)

                        response_text = safe_response_text(
                            response,
                            settings.DOWNLOAD_MAX_BYTE_COUNT,
                        )
                except (
                    RequestException,
                    ResponseTooBig,
                    WrongContentTypeError,
                ):
                    if verbosity >= 2:
                        self.stderr.write(
                            self.style.ERROR(
                                f"unable to load '{feed_url}'\n{traceback.format_exc()}"
                            )
                        )
                    failed_feed_urls.append(feed_url)
                    continue

                d: Any
                try:
                    d = feed_handler.text_2_d(response_text)
                except FeedHandlerError:
                    if verbosity >= 2:
                        self.stderr.write(
                            self.style.ERROR(
                                f"unable to parse '{feed_url}': {traceback.format_exc()}"
                            )
                        )
                    failed_feed_urls.append(feed_url)
                    continue

                feed = feed_handler.d_feed_2_feed(d.feed, feed_url, now)
                feeds.append(feed)
                new_feeds.append(feed)

                for index, d_entry in enumerate(d.get("entries", [])):
                    feed_entry: FeedEntry
                    try:
                        feed_entry = feed_handler.d_entry_2_feed_entry(d_entry, now)
                    except ValueError:  # pragma: no cover
                        if verbosity >= 2:
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

        if failed_feed_urls:
            self.stderr.write(
                self.style.ERROR(f"failed to query: {', '.join(failed_feed_urls)}")
            )

        if save and new_feeds:
            for feed in new_feeds:
                feed.with_subscription_data()
            with transaction.atomic():
                Feed.objects.bulk_create(new_feeds, ignore_conflicts=True)
                FeedEntry.objects.bulk_create(new_feed_entries, ignore_conflicts=True)

        table: list[list[Any]]
        if print_feeds:
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
