import logging
import time
from multiprocessing import Process

from django.test import TestCase

from api import models

from daemons.subscription_setup_daemon import get_first_entry, do_subscription


def _http_server_process():
    import os
    import sys
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    sys.stdout = open('/dev/null', 'w')
    sys.stderr = sys.stdout

    os.chdir('api/tests/test_files/')

    with HTTPServer(('', 8080), SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()


class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('subscription_setup_daemon').setLevel(logging.CRITICAL)

        try:
            cls.user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            cls.user = models.User.objects.create(email='test@test.com')

        cls.http_process = Process(target=_http_server_process)
        cls.http_process.start()

        time.sleep(2.0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        cls.http_process.terminate()

        time.sleep(2.0)

    def test_get_first_entry(self):
        models.FeedSubscriptionProgressEntry.objects.all().delete()

        feed_subscription_progress_entry = get_first_entry()

        self.assertIsNone(feed_subscription_progress_entry)

        feed_subscription_progress_entry = models.FeedSubscriptionProgressEntry.objects.create(user=DaemonTestCase.user)

        self.assertEqual(feed_subscription_progress_entry.status, models.FeedSubscriptionProgressEntry.NOT_STARTED)

        feed_subscription_progress_entry = get_first_entry()

        self.assertIsNotNone(feed_subscription_progress_entry)
        self.assertEqual(feed_subscription_progress_entry.status, models.FeedSubscriptionProgressEntry.STARTED)

    def test_do_subscription(self):
        feed_subscription_progress_entry = models.FeedSubscriptionProgressEntry.objects.create(user=DaemonTestCase.user)

        self.assertEqual(feed_subscription_progress_entry.status, models.FeedSubscriptionProgressEntry.NOT_STARTED)

        feed_subscription_progress_entry_descriptor = models.FeedSubscriptionProgressEntryDescriptor.objects.create(
            feed_subscription_progress_entry=feed_subscription_progress_entry, feed_url='http://localhost:8080/rss_2.0/well_formed.xml')
        self.assertFalse(feed_subscription_progress_entry_descriptor.is_finished)

        feed_subscription_progress_entry_descriptor = models.FeedSubscriptionProgressEntryDescriptor.objects.create(
            feed_subscription_progress_entry=feed_subscription_progress_entry, feed_url='http://localhost:8080/rss_2.0_ns/well_formed.xml', custom_feed_title='Custom Title')
        self.assertFalse(feed_subscription_progress_entry_descriptor.is_finished)

        feed_subscription_progress_entry_descriptor = models.FeedSubscriptionProgressEntryDescriptor.objects.create(
            feed_subscription_progress_entry=feed_subscription_progress_entry, feed_url='http://localhost:8080/atom_1.0/well_formed.xml', user_category_text='User Category')
        self.assertFalse(feed_subscription_progress_entry_descriptor.is_finished)

        feed_subscription_progress_entry_descriptor = models.FeedSubscriptionProgressEntryDescriptor.objects.create(
            feed_subscription_progress_entry=feed_subscription_progress_entry, feed_url='http://localhost:8080/atom_0.3/well_formed.xml', custom_feed_title='Custom Title', user_category_text='User Category')
        self.assertFalse(feed_subscription_progress_entry_descriptor.is_finished)

        feed_subscription_progress_entry = get_first_entry()

        self.assertEqual(feed_subscription_progress_entry.status, models.FeedSubscriptionProgressEntry.STARTED)

        do_subscription(feed_subscription_progress_entry)

        self.assertEqual(feed_subscription_progress_entry.status, models.FeedSubscriptionProgressEntry.FINISHED)
