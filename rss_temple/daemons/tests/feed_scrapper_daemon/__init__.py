import logging
import datetime

from django.test import TestCase

from api import models

from daemons.feed_scrapper_daemon.impl import scrape_feed, new_update_backoff_until, logger


class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_daemon_logger_level = logger().getEffectiveLevel()
        cls.old_app_logger_level = logging.getLogger(
            'rss_temple').getEffectiveLevel()

        logger().setLevel(logging.CRITICAL)
        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)

        cls.feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml', title='Fake Feed', home_url='http://example.com')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logger().setLevel(cls.old_daemon_logger_level)
        logging.getLogger('rss_temple').setLevel(cls.old_app_logger_level)

    def test_scrape_feed(self):
        text = None
        with open('api/tests/test_files/atom_1.0/well_formed.xml', 'r') as f:
            text = f.read()

        scrape_feed(DaemonTestCase.feed, text)

        feed_count = models.Feed.objects.count()
        feed_entry_count = models.FeedEntry.objects.count()

        # do it twice to make sure duplicate entries aren't added
        scrape_feed(DaemonTestCase.feed, text)

        self.assertEqual(feed_count, models.Feed.objects.count())
        self.assertEqual(feed_entry_count, models.FeedEntry.objects.count())

    def test_new_update_backoff_until(self):
        self.assertAlmostEqual(DaemonTestCase.feed.db_created_at.timestamp(), DaemonTestCase.feed.update_backoff_until.timestamp(), delta=1)
        self.assertIsNone(DaemonTestCase.feed.db_updated_at)

        DaemonTestCase.feed.update_backoff_until = DaemonTestCase.feed.db_created_at

        DaemonTestCase.feed.update_backoff_until = new_update_backoff_until(DaemonTestCase.feed)
        self.assertAlmostEqual(DaemonTestCase.feed.update_backoff_until.timestamp(), (DaemonTestCase.feed.db_created_at + datetime.timedelta(seconds=2)).timestamp(), delta=1)

        DaemonTestCase.feed.update_backoff_until = new_update_backoff_until(DaemonTestCase.feed)
        self.assertAlmostEqual(DaemonTestCase.feed.update_backoff_until.timestamp(), (DaemonTestCase.feed.db_created_at + datetime.timedelta(seconds=4)).timestamp(), delta=1)
