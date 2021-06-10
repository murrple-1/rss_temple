import logging
import datetime

from django.test import TestCase

from api import models

from daemons.feed_scrapper_daemon.impl import scrape_feed, success_update_backoff_until, error_update_backoff_until, logger


class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_daemon_logger_level = logger().getEffectiveLevel()
        cls.old_app_logger_level = logging.getLogger(
            'rss_temple').getEffectiveLevel()

        logger().setLevel(logging.CRITICAL)
        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logger().setLevel(cls.old_daemon_logger_level)
        logging.getLogger('rss_temple').setLevel(cls.old_app_logger_level)

    def test_scrape_feed(self):
        feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml', title='Fake Feed', home_url='http://example.com')

        text = None
        with open('api/tests/test_files/atom_1.0/well_formed.xml', 'r') as f:
            text = f.read()

        scrape_feed(feed, text)

        feed_count = models.Feed.objects.count()
        feed_entry_count = models.FeedEntry.objects.count()

        # do it twice to make sure duplicate entries aren't added
        scrape_feed(feed, text)

        self.assertEqual(feed_count, models.Feed.objects.count())
        self.assertEqual(feed_entry_count, models.FeedEntry.objects.count())

    def test_success_update_backoff_until(self):
        feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml', title='Fake Feed', home_url='http://example.com')

        self.assertAlmostEqual(feed.db_created_at.timestamp(
        ), feed.update_backoff_until.timestamp(), delta=1)
        self.assertIsNone(feed.db_updated_at)

        feed.db_updated_at = datetime.datetime.utcnow()

        feed.update_backoff_until = success_update_backoff_until(feed)

        self.assertAlmostEqual(feed.update_backoff_until.timestamp(
        ), (feed.db_updated_at + datetime.timedelta(minutes=1)).timestamp(), delta=1)

    def test_error_update_backoff_until(self):
        feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml', title='Fake Feed', home_url='http://example.com')

        self.assertAlmostEqual(feed.db_created_at.timestamp(
        ), feed.update_backoff_until.timestamp(), delta=1)
        self.assertIsNone(feed.db_updated_at)

        feed.update_backoff_until = feed.db_created_at

        feed.update_backoff_until = error_update_backoff_until(feed)
        self.assertAlmostEqual(feed.update_backoff_until.timestamp(
        ), (feed.db_created_at + datetime.timedelta(seconds=30)).timestamp(), delta=1)

        feed.update_backoff_until = error_update_backoff_until(feed)
        self.assertAlmostEqual(feed.update_backoff_until.timestamp(
        ), (feed.db_created_at + datetime.timedelta(seconds=60)).timestamp(), delta=1)
