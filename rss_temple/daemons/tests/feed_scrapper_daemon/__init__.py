import logging

from django.test import TestCase

from api import models

from daemons.feed_scrapper_daemon import scrape_feed

# TODO write tests
class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('feed_scrapper_daemon').setLevel(logging.CRITICAL)
        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)

        models.Feed.objects.all().delete()

        cls.feed = models.Feed(
            feed_url='http://example.com/rss.xml', title='Fake Feed', home_url='http://example.com')
        cls.feed.save()

    def test_scrape_feed(self):
        text = None
        with open('api/tests/test_files/rss_2.0/well_formed.xml', 'r') as f:
            text = f.read()

        scrape_feed(DaemonTestCase.feed, text)

        # do it twice to make sure duplicate entries aren't added
        scrape_feed(DaemonTestCase.feed, text)
