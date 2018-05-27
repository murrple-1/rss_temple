import datetime
import logging

from django.test import TestCase, Client

from api import models, fields

class FeedTestCase(TestCase):
    # TODO
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.disable(logging.CRITICAL)

        user = None
        try:
            user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User()
            user.email = 'test@test.com'

            user.save()

        session = models.Session()
        session.user = user
        session.expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=2))

        session.save()

        cls.session_token = str(session.uuid)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.disable(logging.NOTSET)

    def test_feed_get(self):
        c = Client()
        response = c.get('/api/feed', {
            'url': 'http://www.feedforall.com/sample.xml',
            'fields': ','.join(fields.field_list('feed')),
            }, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token)
        self.assertEqual(response.status_code, 200)

    def test_feeds_get(self):
        c = Client()
        response = c.get('/api/feeds', { 'fields': ','.join(fields.field_list('feed')) }, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token)
        self.assertEqual(response.status_code, 200)

    def test_feed_subscribe_post_delete(self):
        c = Client()
        response = c.post('/api/feed/subscribe?url=http://www.feedforall.com/sample.xml', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token)
        self.assertEqual(response.status_code, 200)

        response = c.delete('/api/feed/subscribe?url=http://www.feedforall.com/sample.xml', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token)
        self.assertEqual(response.status_code, 200)
