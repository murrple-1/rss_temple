import datetime
import logging
from io import StringIO
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from api.management.commands.feedscrapperdaemon import Command
from api.models import Feed, FeedEntry
from api.tests.utils import db_migrations_state

if TYPE_CHECKING:
    from unittest.mock import _Mock, _patch


class DaemonTestCase(TestCase):
    old_app_logger_level: ClassVar[int]
    command: ClassVar[Command]
    stdout_patcher: ClassVar["_patch[_Mock]"]
    stderr_patcher: ClassVar["_patch[_Mock]"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)

        cls.command = Command()
        cls.stdout_patcher = patch.object(cls.command, "stdout", new_callable=StringIO)
        cls.stderr_patcher = patch.object(cls.command, "stderr", new_callable=StringIO)

    def setUp(self):
        super().setUp()

        self.stdout_patcher.start()
        self.stderr_patcher.start()

        db_migrations_state()

    def tearDown(self):
        super().tearDown()

        self.stdout_patcher.stop()
        self.stderr_patcher.stop()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)

    def test_scrape_feed(self):
        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Fake Feed",
            home_url="http://example.com",
        )

        text: str
        with open("api/tests/test_files/atom_1.0/well_formed.xml", "r") as f:
            text = f.read()

        self.command._scrape_feed(feed, text)

        feed_count = Feed.objects.count()
        feed_entry_count = FeedEntry.objects.count()

        # do it twice to make sure duplicate entries aren't added
        self.command._scrape_feed(feed, text)

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

            feed.update_backoff_until = self.command._success_update_backoff_until(
                feed, settings.SUCCESS_BACKOFF_SECONDS
            )

            self.assertAlmostEqual(
                feed.update_backoff_until.timestamp(),
                (feed.db_updated_at + datetime.timedelta(seconds=60)).timestamp(),
                delta=1,
            )

    def test_error_update_backoff_until(self):
        with self.settings(MIN_ERROR_BACKOFF_SECONDS=60, MAX_ERROR_BACKOFF_SECONDS=110):
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

            feed.update_backoff_until = self.command._error_update_backoff_until(
                feed,
                settings.MIN_ERROR_BACKOFF_SECONDS,
                settings.MAX_ERROR_BACKOFF_SECONDS,
            )
            self.assertAlmostEqual(
                feed.update_backoff_until.timestamp(),
                (feed.db_created_at + datetime.timedelta(seconds=60)).timestamp(),
                delta=1,
            )

            feed.update_backoff_until = self.command._error_update_backoff_until(
                feed,
                settings.MIN_ERROR_BACKOFF_SECONDS,
                settings.MAX_ERROR_BACKOFF_SECONDS,
            )
            self.assertAlmostEqual(
                feed.update_backoff_until.timestamp(),
                (feed.db_created_at + datetime.timedelta(seconds=120)).timestamp(),
                delta=1,
            )

            feed.update_backoff_until = self.command._error_update_backoff_until(
                feed,
                settings.MIN_ERROR_BACKOFF_SECONDS,
                settings.MAX_ERROR_BACKOFF_SECONDS,
            )
            self.assertAlmostEqual(
                feed.update_backoff_until.timestamp(),
                (feed.db_created_at + datetime.timedelta(seconds=230)).timestamp(),
                delta=1,
            )
