import logging
import time
import datetime
from multiprocessing import Process

from django.test import TestCase

from api import models
from api.tests.http_server import http_server_target

from daemons.subscription_setup_daemon import get_first_entry, do_subscription


class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('subscription_setup_daemon').setLevel(
            logging.CRITICAL)

        cls.user = models.User.objects.create(email='test@test.com')

        cls.http_process = Process(target=http_server_target, args=(8080,))
        cls.http_process.start()

        time.sleep(2.0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        cls.http_process.terminate()

        time.sleep(2.0)

    def test_get_first_entry(self):
        feed_subscription_progress_entry = get_first_entry()

        self.assertIsNone(feed_subscription_progress_entry)

        feed_subscription_progress_entry = models.FeedSubscriptionProgressEntry.objects.create(
            user=DaemonTestCase.user)

        self.assertEqual(feed_subscription_progress_entry.status,
                         models.FeedSubscriptionProgressEntry.NOT_STARTED)

        feed_subscription_progress_entry = get_first_entry()

        self.assertIsNotNone(feed_subscription_progress_entry)
        self.assertEqual(feed_subscription_progress_entry.status,
                         models.FeedSubscriptionProgressEntry.STARTED)

    def test_do_subscription(self):
        feed1 = models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml?_=existing',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed2 = models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml?_=existing_with_custom_title',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed1,
            user=DaemonTestCase.user)
        models.SubscribedFeedUserMapping.objects.create(
            feed=feed2,
            user=DaemonTestCase.user,
            custom_feed_title='Old Custom Title')

        models.UserCategory.objects.create(
            user=DaemonTestCase.user, text='Old User Category')

        feed_subscription_progress_entry = models.FeedSubscriptionProgressEntry.objects.create(
            user=DaemonTestCase.user)

        self.assertEqual(feed_subscription_progress_entry.status,
                         models.FeedSubscriptionProgressEntry.NOT_STARTED)

        count = 0
        for feed_url in ['http://localhost:8080/rss_2.0/well_formed.xml', 'http://localhost:8080/rss_2.0/well_formed.xml?_={s}', 'http://localhost:8080/rss_2.0/sample-404.xml', 'http://localhost:8080/rss_2.0/sample-404.xml?_={s}']:
            for custom_feed_title in [None, 'Old Custom Title', 'New Custom Title', 'New Custom Title {s}', 'Sample Feed']:
                for user_category_text in [None, 'Old User Category', 'New User Category', 'New User Category {s}']:
                    feed_subscription_progress_entry_descriptor = models.FeedSubscriptionProgressEntryDescriptor.objects.create(
                        feed_subscription_progress_entry=feed_subscription_progress_entry,
                        feed_url=feed_url.format(s=count),
                        custom_feed_title=None if custom_feed_title is None else custom_feed_title.format(
                            s=count),
                        user_category_text=None if user_category_text is None else user_category_text.format(s=count))
                    self.assertFalse(
                        feed_subscription_progress_entry_descriptor.is_finished)

                    count += 1

        feed_subscription_progress_entry = get_first_entry()

        self.assertEqual(feed_subscription_progress_entry.status,
                         models.FeedSubscriptionProgressEntry.STARTED)

        do_subscription(feed_subscription_progress_entry)

        self.assertEqual(feed_subscription_progress_entry.status,
                         models.FeedSubscriptionProgressEntry.FINISHED)
