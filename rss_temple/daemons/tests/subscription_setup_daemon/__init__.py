import logging
import time
import datetime
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
        feed1 = None
        try:
            feed1 = models.Feed.objects.get(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml?_=existing')
        except models.Feed.DoesNotExist:
            feed1 = models.Feed.objects.create(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml?_=existing',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)

        feed2 = None
        try:
            feed2 = models.Feed.objects.get(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml?_=existing_with_custom_title')
        except models.Feed.DoesNotExist:
            feed2 = models.Feed.objects.create(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml?_=existing_with_custom_title',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)

        models.SubscribedFeedUserMapping.objects.filter(user=DaemonTestCase.user).delete()
        models.SubscribedFeedUserMapping.objects.create(
            feed=feed1,
            user=DaemonTestCase.user)
        models.SubscribedFeedUserMapping.objects.create(
            feed=feed2,
            user=DaemonTestCase.user,
            custom_feed_title='Old Custom Title')

        try:
            models.UserCategory.objects.get(user=DaemonTestCase.user, text='Old User Category')
        except models.UserCategory.DoesNotExist:
            models.UserCategory.objects.create(user=DaemonTestCase.user, text='Old User Category')

        feed_subscription_progress_entry = models.FeedSubscriptionProgressEntry.objects.create(user=DaemonTestCase.user)

        self.assertEqual(feed_subscription_progress_entry.status, models.FeedSubscriptionProgressEntry.NOT_STARTED)

        count = 0
        for feed_url in ['http://localhost:8080/rss_2.0/well_formed.xml', 'http://localhost:8080/rss_2.0/well_formed.xml?_={s}', 'http://localhost:8080/rss_2.0/sample-404.xml', 'http://localhost:8080/rss_2.0/sample-404.xml?_={s}']:
            for custom_feed_title in [None, 'Old Custom Title', 'New Custom Title', 'New Custom Title {s}', 'Sample Feed']:
                for user_category_text in [None, 'Old User Category', 'New User Category', 'New User Category {s}']:
                    feed_subscription_progress_entry_descriptor = models.FeedSubscriptionProgressEntryDescriptor.objects.create(
                        feed_subscription_progress_entry=feed_subscription_progress_entry,
                        feed_url=feed_url.format(s=count),
                        custom_feed_title=None if custom_feed_title is None else custom_feed_title.format(s=count),
                        user_category_text=None if user_category_text is None else user_category_text.format(s=count))
                    self.assertFalse(feed_subscription_progress_entry_descriptor.is_finished)

                    count += 1

        feed_subscription_progress_entry = get_first_entry()

        self.assertEqual(feed_subscription_progress_entry.status, models.FeedSubscriptionProgressEntry.STARTED)

        do_subscription(feed_subscription_progress_entry)

        self.assertEqual(feed_subscription_progress_entry.status, models.FeedSubscriptionProgressEntry.FINISHED)