import logging
from typing import Iterable, cast

import requests.exceptions
from django.db import transaction
from django.utils import timezone

from api import feed_handler, rss_requests
from api.models import (
    Feed,
    FeedEntry,
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
    SubscribedFeedUserMapping,
    UserCategory,
)
from api.requests_extensions import safe_response_text
from api.text_classifier.lang_detector import detect_iso639_3
from api.text_classifier.prep_content import prep_for_lang_detection

_logger = logging.getLogger("rss_temple")


def setup_subscriptions(
    feed_subscription_progress_entry: FeedSubscriptionProgressEntry,
    response_max_size=1024 * 1000,
    response_chunk_size=1024,
):  # pragma: testing-subscription-setup-daemon-do-subscription
    feeds: dict[str, Feed] = {}
    subscriptions: set[str] = set()
    custom_titles: set[str] = set()
    for mapping in SubscribedFeedUserMapping.objects.select_related("feed").filter(
        user_id=feed_subscription_progress_entry.user_id
    ):
        subscriptions.add(mapping.feed.feed_url)
        if mapping.custom_feed_title is not None:
            custom_titles.add(mapping.custom_feed_title)

    user_categories: dict[str, UserCategory] = {}
    user_category_mapping_dict: dict[str, set[str]] = {}
    for user_category in UserCategory.objects.filter(
        user_id=feed_subscription_progress_entry.user_id
    ):
        user_categories[user_category.text] = user_category
        user_category_mapping_dict[user_category.text] = set(
            cast(
                Iterable[str],
                user_category.feeds.values_list("feed_url", flat=True),
            )
        )

    for (
        feed_subscription_progress_entry_descriptor
    ) in FeedSubscriptionProgressEntryDescriptor.objects.filter(
        feed_subscription_progress_entry=feed_subscription_progress_entry,
        is_finished=False,
    ):
        feed_url = feed_subscription_progress_entry_descriptor.feed_url

        feed = feeds.get(feed_url)
        if feed is None:
            try:
                feed = Feed.objects.get(feed_url=feed_url)
            except Feed.DoesNotExist:
                try:
                    feed = _generate_feed(
                        feed_url, response_max_size, response_chunk_size
                    )
                except (
                    requests.exceptions.RequestException,
                    feed_handler.FeedHandlerError,
                ):
                    _logger.exception("could not load feed for '%s'", feed_url)
                    continue

            feeds[feed_url] = cast(Feed, feed)

        if feed is not None:
            if feed_url not in subscriptions:
                custom_title: str | None = (
                    feed_subscription_progress_entry_descriptor.custom_feed_title
                )

                if custom_title is not None and custom_title in custom_titles:
                    custom_title = None

                if custom_title is not None and feed.title == custom_title:
                    custom_title = None

                SubscribedFeedUserMapping.objects.create(
                    feed=feed,
                    user_id=feed_subscription_progress_entry.user_id,
                    custom_feed_title=custom_title,
                )

                subscriptions.add(feed_url)

                if custom_title is not None:
                    custom_titles.add(custom_title)

            if (
                feed_subscription_progress_entry_descriptor.user_category_text
                is not None
            ):
                user_category_text = (
                    feed_subscription_progress_entry_descriptor.user_category_text
                )

                user_category_ = user_categories.get(user_category_text)

                if user_category_ is None:
                    user_category_ = UserCategory.objects.create(
                        user_id=feed_subscription_progress_entry.user_id,
                        text=user_category_text,
                    )

                    user_categories[user_category_text] = user_category_

                user_category_feeds = user_category_mapping_dict.get(user_category_text)

                if user_category_feeds is None:
                    user_category_feeds = set()

                    user_category_mapping_dict[user_category_text] = user_category_feeds

                if feed_url not in user_category_feeds:
                    user_category_.feeds.add(feed)

                    user_category_feeds.add(feed_url)

        feed_subscription_progress_entry_descriptor.is_finished = True
        feed_subscription_progress_entry_descriptor.save()

    feed_subscription_progress_entry.status = FeedSubscriptionProgressEntry.FINISHED
    feed_subscription_progress_entry.save()


def _generate_feed(
    url: str,
    response_max_size: int,
    response_chunk_size: int,
):  # pragma: testing-subscription-setup-daemon-do-subscription
    response = rss_requests.get(url, stream=True)
    response.raise_for_status()

    now = timezone.now()

    response_text = safe_response_text(response, response_max_size, response_chunk_size)

    d = feed_handler.text_2_d(response_text)
    feed = feed_handler.d_feed_2_feed(d.feed, url, now)
    feed.save()

    feed_entries: list[FeedEntry] = []

    for d_entry in d.get("entries", []):
        feed_entry: FeedEntry
        try:
            feed_entry = feed_handler.d_entry_2_feed_entry(d_entry, now)
        except ValueError:
            continue

        feed_entry.feed = feed

        feed_entry.language_id = detect_iso639_3(
            prep_for_lang_detection(feed_entry.title, feed_entry.content)
        )

        feed_entries.append(feed_entry)

    FeedEntry.objects.bulk_create(feed_entries, ignore_conflicts=True)

    return feed


def get_first_entry():
    with transaction.atomic():
        feed_subscription_progress_entry = (
            FeedSubscriptionProgressEntry.objects.filter(
                status=FeedSubscriptionProgressEntry.NOT_STARTED
            )
            .select_for_update(skip_locked=True)
            .first()
        )

        if feed_subscription_progress_entry is not None:
            feed_subscription_progress_entry.status = (
                FeedSubscriptionProgressEntry.STARTED
            )
            feed_subscription_progress_entry.save()

        return feed_subscription_progress_entry
