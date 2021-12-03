import logging
import datetime
import uuid
import random

from api.tests.views import ViewTestCase
from api import models


class ProgressTestCase(ViewTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger(
            'rss_temple').getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger(
            'django').getEffectiveLevel()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger('rss_temple').setLevel(cls.old_app_logger_level)
        logging.getLogger('django').setLevel(cls.old_django_logger_level)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = models.User.objects.create(email='test@test.com')

        cls.session = models.Session.objects.create(
            user=cls.user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))

        cls.session_token = cls.session.uuid
        cls.session_token_str = str(cls.session.uuid)

    @staticmethod
    def generate_entry(desc_count=10):
        feed_subscription_progress_entry = models.FeedSubscriptionProgressEntry.objects.create(
            user=ProgressTestCase.user)

        feed_subscription_progress_entry_descriptors = []

        for step in range(desc_count):
            feed_subscription_progress_entry_descriptor = models.FeedSubscriptionProgressEntryDescriptor.objects.create(
                feed_subscription_progress_entry=feed_subscription_progress_entry,
                feed_url=f'http://localhost:8080/rss_2.0/well_formed.xml?_={step}')

            feed_subscription_progress_entry_descriptors.append(
                feed_subscription_progress_entry_descriptor)

        return feed_subscription_progress_entry, feed_subscription_progress_entry_descriptors

    def test_feed_subscription_progress_get_404(self):
        response = self.client.get(f'/api/feed/subscribe/progress/{uuid.uuid4()}',
                                   HTTP_X_SESSION_TOKEN=ProgressTestCase.session_token_str)
        self.assertEqual(response.status_code, 404, response.content)

    def test_feed_subscription_progress_get_not_started(self):
        feed_subscription_progress_entry, feed_subscription_progress_entry_descriptors = ProgressTestCase.generate_entry()

        response = self.client.get(f'/api/feed/subscribe/progress/{feed_subscription_progress_entry.uuid}',
                                   HTTP_X_SESSION_TOKEN=ProgressTestCase.session_token_str)
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn('state', json_)
        self.assertEqual(json_['state'], 'notstarted')

    def test_feed_subscription_progress_get_started(self):
        feed_subscription_progress_entry, feed_subscription_progress_entry_descriptors = ProgressTestCase.generate_entry()

        feed_subscription_progress_entry.status = models.FeedSubscriptionProgressEntry.STARTED
        feed_subscription_progress_entry.save()

        feed_subscription_progress_entry_descriptor = feed_subscription_progress_entry_descriptors[
            0]
        feed_subscription_progress_entry_descriptor.is_finished = True
        feed_subscription_progress_entry_descriptor.save()

        finished_count = 1

        for feed_subscription_progress_entry_descriptor in feed_subscription_progress_entry_descriptors[2:]:
            if random.choice([True, False]):
                feed_subscription_progress_entry_descriptor.is_finished = True
                feed_subscription_progress_entry_descriptor.save()
                finished_count += 1

        response = self.client.get(f'/api/feed/subscribe/progress/{feed_subscription_progress_entry.uuid}',
                                   HTTP_X_SESSION_TOKEN=ProgressTestCase.session_token_str)
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn('state', json_)
        self.assertEqual(json_['state'], 'started')
        self.assertIn('totalCount', json_)
        self.assertEqual(json_['totalCount'], len(
            feed_subscription_progress_entry_descriptors))
        self.assertIn('finishedCount', json_)
        self.assertEqual(json_['finishedCount'], finished_count)

    def test_feed_subscription_progress_get_finished(self):
        feed_subscription_progress_entry, feed_subscription_progress_entry_descriptors = ProgressTestCase.generate_entry()

        feed_subscription_progress_entry.status = models.FeedSubscriptionProgressEntry.FINISHED
        feed_subscription_progress_entry.save()

        for feed_subscription_progress_entry_descriptor in feed_subscription_progress_entry_descriptors:
            feed_subscription_progress_entry_descriptor.is_finished = True
            feed_subscription_progress_entry_descriptor.save()

        response = self.client.get(f'/api/feed/subscribe/progress/{feed_subscription_progress_entry.uuid}',
                                   HTTP_X_SESSION_TOKEN=ProgressTestCase.session_token_str)
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn('state', json_)
        self.assertEqual(json_['state'], 'finished')
