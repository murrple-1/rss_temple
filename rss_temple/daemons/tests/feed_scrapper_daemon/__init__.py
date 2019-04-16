import logging

from django.test import TestCase

from api import models

from daemons.feed_scrapper_daemon import scrape_feed


class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('feed_scrapper_daemon').setLevel(logging.CRITICAL)
        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)

        models.Feed.objects.all().delete()

        cls.feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml', title='Fake Feed', home_url='http://example.com')

    def test_scrape_feed(self):
        text = None
        with open('api/tests/test_files/rss_2.0/well_formed.xml', 'r') as f:
            text = f.read()

        scrape_feed(DaemonTestCase.feed, text)

        feed_count = models.Feed.objects.count()
        feed_entry_count = models.FeedEntry.objects.count()

        # do it twice to make sure duplicate entries aren't added
        scrape_feed(DaemonTestCase.feed, text)

        self.assertEqual(feed_count, models.Feed.objects.count())
        self.assertEqual(feed_entry_count, models.FeedEntry.objects.count())
