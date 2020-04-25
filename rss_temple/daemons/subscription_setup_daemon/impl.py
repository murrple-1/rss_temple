

import logging
import sys

from django.db import transaction

import requests

from api import models, feed_handler, rss_requests
from api.exceptions import QueryException


_logger = None

def logger():  # pragma: no cover
    global _logger

    if _logger is None:
        _logger = logging.getLogger('subscription_setup_daemon')

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(stream_handler)

        file_handler = logging.handlers.RotatingFileHandler(
            filename='subscription_setup_daemon.log', maxBytes=(
                50 * 100000), backupCount=3)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(file_handler)

    return _logger


def get_first_entry():
    with transaction.atomic():
        feed_subscription_progress_entry = models.FeedSubscriptionProgressEntry.objects.filter(
            status=models.FeedSubscriptionProgressEntry.NOT_STARTED).select_for_update(skip_locked=True).first()

        if feed_subscription_progress_entry is not None:
            feed_subscription_progress_entry.status = models.FeedSubscriptionProgressEntry.STARTED
            feed_subscription_progress_entry.save()

        return feed_subscription_progress_entry


def do_subscription(feed_subscription_progress_entry):  # pragma: local cover
    feeds = {}
    subscriptions = set()
    custom_titles = set()
    for mapping in models.SubscribedFeedUserMapping.objects.select_related('feed').filter(user_id=feed_subscription_progress_entry.user_id):
        subscriptions.add(mapping.feed.feed_url)
        if mapping.custom_feed_title is not None:
            custom_titles.add(mapping.custom_feed_title)

    user_categories = {}
    user_category_mapping_dict = {}
    for user_category in models.UserCategory.objects.filter(user_id=feed_subscription_progress_entry.user_id):
        user_categories[user_category.text] = user_category
        user_category_mapping_dict[user_category.text] = set(models.FeedUserCategoryMapping.objects.filter(
            user_category=user_category).values_list('feed__feed_url'))

    for feed_subscription_progress_entry_descriptor in models.FeedSubscriptionProgressEntryDescriptor.objects.filter(feed_subscription_progress_entry=feed_subscription_progress_entry, is_finished=False):
        feed_url = feed_subscription_progress_entry_descriptor.feed_url

        feed = feeds.get(feed_url)
        if feed is None:
            try:
                feed = models.Feed.objects.get(feed_url=feed_url)
            except models.Feed.DoesNotExist:
                try:
                    feed = _generate_feed(feed_url)
                except (requests.exceptions.RequestException, QueryException):
                    logger().exception('could not load feed for \'%s\'', feed_url)
                    pass

            feeds[feed_url] = feed

        if feed is not None:
            if feed_url not in subscriptions:
                custom_title = feed_subscription_progress_entry_descriptor.custom_feed_title

                if custom_title is not None and custom_title in custom_titles:
                    custom_title = None

                if custom_title is not None and feed.title == custom_title:
                    custom_title = None

                models.SubscribedFeedUserMapping.objects.create(
                    feed=feed, user_id=feed_subscription_progress_entry.user_id, custom_feed_title=custom_title)

                subscriptions.add(feed_url)

                if custom_title is not None:
                    custom_titles.add(custom_title)

            if feed_subscription_progress_entry_descriptor.user_category_text is not None:
                user_category_text = feed_subscription_progress_entry_descriptor.user_category_text

                user_category = user_categories.get(user_category_text)

                if user_category is None:
                    user_category = models.UserCategory.objects.create(
                        user_id=feed_subscription_progress_entry.user_id, text=user_category_text)

                    user_categories[user_category_text] = user_category

                user_category_feeds = user_category_mapping_dict.get(
                    user_category_text)

                if user_category_feeds is None:
                    user_category_feeds = set()

                    user_category_mapping_dict[user_category_text] = user_category_feeds

                if feed_url not in user_category_feeds:
                    models.FeedUserCategoryMapping.objects.create(
                        feed=feed, user_category=user_category)

                    user_category_feeds.add(feed_url)

        feed_subscription_progress_entry_descriptor.is_finished = True
        feed_subscription_progress_entry_descriptor.save()

    feed_subscription_progress_entry.status = models.FeedSubscriptionProgressEntry.FINISHED
    feed_subscription_progress_entry.save()


def _generate_feed(url):  # pragma: local cover
    response = rss_requests.get(url)
    response.raise_for_status()

    d = feed_handler.text_2_d(response.text)
    feed = feed_handler.d_feed_2_feed(d.feed, url)
    feed.save()

    feed_entries = []

    for d_entry in d.get('entries', []):
        feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
        feed_entry.feed = feed
        feed_entries.append(feed_entry)

    models.FeedEntry.objects.bulk_create(feed_entries)

    return feed
