import logging
import logging.handlers
import sys
import time

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from api import feed_handler, rss_requests
from api.models import (
    Feed,
    FeedEntry,
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
    SubscribedFeedUserMapping,
    UserCategory,
)

_logger: logging.Logger | None = None


def logger():  # pragma: no cover
    global _logger

    if _logger is None:
        _logger = logging.getLogger("subscription_setup_daemon")
        _logger.setLevel(logging.DEBUG)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s (%(levelname)s): %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        _logger.addHandler(stream_handler)

        file_handler = logging.handlers.RotatingFileHandler(
            filename="subscription_setup_daemon.log",
            maxBytes=(50 * 100000),
            backupCount=3,
        )
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s (%(levelname)s): %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        _logger.addHandler(file_handler)

    return _logger


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


def do_subscription(
    feed_subscription_progress_entry,
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
            user_category.feeds.values_list("feed_url")
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
                    feed = _generate_feed(feed_url)
                except requests.exceptions.RequestException:
                    logger().exception("could not load feed for '%s'", feed_url)
                    continue

            feeds[feed_url] = feed

        if feed is not None:
            if feed_url not in subscriptions:
                custom_title = (
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

                user_category = user_categories.get(user_category_text)

                if user_category is None:
                    user_category = UserCategory.objects.create(
                        user_id=feed_subscription_progress_entry.user_id,
                        text=user_category_text,
                    )

                    user_categories[user_category_text] = user_category

                user_category_feeds = user_category_mapping_dict.get(user_category_text)

                if user_category_feeds is None:
                    user_category_feeds = set()

                    user_category_mapping_dict[user_category_text] = user_category_feeds

                if feed_url not in user_category_feeds:
                    user_category.feeds.add(feed)

                    user_category_feeds.add(feed_url)

        feed_subscription_progress_entry_descriptor.is_finished = True
        feed_subscription_progress_entry_descriptor.save()

    feed_subscription_progress_entry.status = FeedSubscriptionProgressEntry.FINISHED
    feed_subscription_progress_entry.save()


def _generate_feed(url):  # pragma: testing-subscription-setup-daemon-do-subscription
    response = rss_requests.get(url)
    response.raise_for_status()

    d = feed_handler.text_2_d(response.text)
    feed = feed_handler.d_feed_2_feed(d.feed, url)
    feed.save()

    feed_entries = []

    for d_entry in d.get("entries", []):
        feed_entry: FeedEntry
        try:
            feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
        except ValueError:
            continue

        feed_entry.feed = feed
        feed_entries.append(feed_entry)

    FeedEntry.objects.bulk_create(feed_entries)

    return feed


class Command(BaseCommand):
    help = "TODO help text"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        try:
            while True:
                feed_subscription_progress_entry = get_first_entry()
                if feed_subscription_progress_entry is not None:
                    logger().info("starting subscription processing...")
                    do_subscription(feed_subscription_progress_entry)
                else:
                    logger().info("no subscription process available. sleeping...")
                    time.sleep(5)
        except Exception:
            logger().exception("loop stopped unexpectedly")
            raise
