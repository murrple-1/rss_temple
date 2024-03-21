import datetime
import logging
from typing import ClassVar

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from api.models import Feed, FeedEntry
from api.tasks.feed_scrape import (
    error_update_backoff_until,
    feed_scrape,
    success_update_backoff_until,
)
from api.tests.utils import db_migrations_state


class TaskTestCase(TestCase):
    old_app_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)

    def setUp(self):
        super().setUp()

        db_migrations_state()

    def test_scrape_feed(self):
        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Fake Feed",
            home_url="http://example.com",
        )

        text: str
        with open("api/tests/test_files/atom_1.0/well_formed.xml", "r") as f:
            text = f.read()

        feed_scrape(feed, text)

        feed_count = Feed.objects.count()
        feed_entry_count = FeedEntry.objects.count()

        # do it twice to make sure duplicate entries aren't added
        feed_scrape(feed, text)

        self.assertEqual(feed_count, Feed.objects.count())
        self.assertEqual(feed_entry_count, FeedEntry.objects.count())

    def test_success_update_backoff_until(self):
        with self.settings(SUCCESS_BACKOFF_SECONDS=60):
            feed = Feed.objects.create(
                feed_url="http://example.com/rss.xml",
                title="Fake Feed",
                home_url="http://example.com",
            )

            self.assertAlmostEqual(
                feed.db_created_at.timestamp(),
                feed.update_backoff_until.timestamp(),
                delta=1,
            )
            self.assertIsNone(feed.db_updated_at)

            feed.db_updated_at = timezone.now()

            feed.update_backoff_until = success_update_backoff_until(
                feed, settings.SUCCESS_BACKOFF_SECONDS
            )

            self.assertAlmostEqual(
                feed.update_backoff_until.timestamp(),
                (feed.db_updated_at + datetime.timedelta(seconds=60)).timestamp(),
                delta=1,
            )

    def test_error_update_backoff_until(self):
        with self.settings(
            MIN_ERROR_BACKOFF_SECONDS=60.0, MAX_ERROR_BACKOFF_SECONDS=220.0
        ):
            feed = Feed.objects.create(
                feed_url="http://example.com/rss.xml",
                title="Fake Feed",
                home_url="http://example.com",
            )

            self.assertAlmostEqual(
                feed.db_created_at.timestamp(),
                feed.update_backoff_until.timestamp(),
                delta=1,
            )
            self.assertIsNone(feed.db_updated_at)

            feed.update_backoff_until = feed.db_created_at

            feed.update_backoff_until = error_update_backoff_until(
                feed,
                settings.MIN_ERROR_BACKOFF_SECONDS,
                settings.MAX_ERROR_BACKOFF_SECONDS,
            )
            self.assertAlmostEqual(
                feed.update_backoff_until.timestamp(),
                (feed.db_created_at + datetime.timedelta(seconds=60.0)).timestamp(),
                delta=1,
            )

            feed.update_backoff_until = error_update_backoff_until(
                feed,
                settings.MIN_ERROR_BACKOFF_SECONDS,
                settings.MAX_ERROR_BACKOFF_SECONDS,
            )
            self.assertAlmostEqual(
                feed.update_backoff_until.timestamp(),
                (feed.db_created_at + datetime.timedelta(seconds=120.0)).timestamp(),
                delta=1,
            )

            feed.update_backoff_until = error_update_backoff_until(
                feed,
                settings.MIN_ERROR_BACKOFF_SECONDS,
                settings.MAX_ERROR_BACKOFF_SECONDS,
            )
            self.assertAlmostEqual(
                feed.update_backoff_until.timestamp(),
                (feed.db_created_at + datetime.timedelta(seconds=220.0)).timestamp(),
                delta=1,
            )
