import logging
import datetime
import uuid
import random

from django.test import TestCase, Client
from django.core.management import call_command

from api import models

class ProgressTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

        try:
            cls.user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            cls.user = models.User.objects.create(email='test@test.com')

        session = models.Session.objects.create(
            user=cls.user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

    @staticmethod
    def generate_entry(desc_count=10):
        feed_subscription_progress_entry = models.FeedSubscriptionProgressEntry.objects.create(user=ProgressTestCase.user)

        feed_subscription_progress_entry_descriptors = []

        for step in range(desc_count):
            feed_subscription_progress_entry_descriptor = models.FeedSubscriptionProgressEntryDescriptor.objects.create(
                feed_subscription_progress_entry=feed_subscription_progress_entry,
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml?_={s}'.format(s=step))

            feed_subscription_progress_entry_descriptors.append(feed_subscription_progress_entry_descriptor)

        return feed_subscription_progress_entry, feed_subscription_progress_entry_descriptors

    def test_feed_subscription_progress_get_404(self):
        c = Client()

        response = c.get('/api/feed/subscribe/progress/{}'.format(str(uuid.uuid4())),
            HTTP_X_SESSION_TOKEN=ProgressTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feed_subscription_progress_get_not_started(self):
        feed_subscription_progress_entry, feed_subscription_progress_entry_descriptors = ProgressTestCase.generate_entry()

        c = Client()

        response = c.get('/api/feed/subscribe/progress/{}'.format(str(feed_subscription_progress_entry.uuid)),
            HTTP_X_SESSION_TOKEN=ProgressTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        _json = response.json()

        self.assertIsInstance(_json, dict)
        self.assertIn('state', _json)
        self.assertEqual(_json['state'], 'notstarted')

    def test_feed_subscription_progress_get_started(self):
        feed_subscription_progress_entry, feed_subscription_progress_entry_descriptors = ProgressTestCase.generate_entry()

        feed_subscription_progress_entry.status = models.FeedSubscriptionProgressEntry.STARTED
        feed_subscription_progress_entry.save()

        feed_subscription_progress_entry_descriptor = feed_subscription_progress_entry_descriptors[0]
        feed_subscription_progress_entry_descriptor.is_finished = True
        feed_subscription_progress_entry_descriptor.save()

        finished_count = 1

        for feed_subscription_progress_entry_descriptor in feed_subscription_progress_entry_descriptors[2:]:
            if random.choice([True, False]):
                feed_subscription_progress_entry_descriptor.is_finished = True
                feed_subscription_progress_entry_descriptor.save()
                finished_count += 1

        c = Client()

        response = c.get('/api/feed/subscribe/progress/{}'.format(str(feed_subscription_progress_entry.uuid)),
            HTTP_X_SESSION_TOKEN=ProgressTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        _json = response.json()

        self.assertIsInstance(_json, dict)
        self.assertIn('state', _json)
        self.assertEqual(_json['state'], 'started')
        self.assertIn('totalCount', _json)
        self.assertEqual(_json['totalCount'], len(feed_subscription_progress_entry_descriptors))
        self.assertIn('finishedCount', _json)
        self.assertEqual(_json['finishedCount'], finished_count)

    def test_feed_subscription_progress_get_finished(self):
        feed_subscription_progress_entry, feed_subscription_progress_entry_descriptors = ProgressTestCase.generate_entry()

        feed_subscription_progress_entry.status = models.FeedSubscriptionProgressEntry.FINISHED
        feed_subscription_progress_entry.save()

        for feed_subscription_progress_entry_descriptor in feed_subscription_progress_entry_descriptors:
            feed_subscription_progress_entry_descriptor.is_finished = True
            feed_subscription_progress_entry_descriptor.save()

        c = Client()

        response = c.get('/api/feed/subscribe/progress/{}'.format(str(feed_subscription_progress_entry.uuid)),
            HTTP_X_SESSION_TOKEN=ProgressTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        _json = response.json()

        self.assertIsInstance(_json, dict)
        self.assertIn('state', _json)
        self.assertEqual(_json['state'], 'finished')
