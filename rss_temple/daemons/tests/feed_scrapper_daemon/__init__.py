import logging

from django.test import TestCase

from daemons.feed_scrapper_daemon import scrape_feed

# TODO write tests
class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('session_cleanup_daemon').setLevel(logging.CRITICAL)

    def test_scrape_feed(self):
        pass
