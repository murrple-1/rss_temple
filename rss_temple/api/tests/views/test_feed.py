import datetime
import logging

from django.test import TestCase, Client

import ujson

from api import models, fields

class FeedTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.disable(logging.CRITICAL)

        user = None
        try:
            user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User(
                email='test@test.com')

            user.save()

        cls.user = user

        session = models.Session()
        session.user = user
        session.expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=2))

        session.save()

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.disable(logging.NOTSET)

    def test_feed_get(self):
        c = Client()
        response = c.get('/api/feed', {
            'url': 'http://www.feedforall.com/sample.xml',
            'fields': ','.join(fields.field_list('feed')),
            }, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feed_get_no_url(self):
        c = Client()
        response = c.get('/api/feed', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_feed_get_non_rss_url(self):
        c = Client()
        response = c.get('/api/feed', {
            'url': 'http://www.feedforall.com/bad.xml',
            }, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feeds_get(self):
        feed = None
        try:
            feed = models.Feed.objects.get(feed_url='http://www.feedforall.com/sample.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://www.feedforall.com/sample.xml',
                is_new=False,
                title='FeedForAll Sample Feed',
                home_url='http://www.feedforall.com/industry-solutions.htm',
                published_at=datetime.datetime.utcnow(),
                updated_at=None)
            feed.save()

        c = Client()
        response = c.get('/api/feeds', { 'fields': ','.join(fields.field_list('feed')) }, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        _json = ujson.loads(response.content)

        self.assertIsInstance(_json, dict)
        self.assertIn('objects', _json)
        self.assertIsInstance(_json['objects'], list)
        self.assertGreaterEqual(len(_json['objects']), 1)

    def test_feed_subscribe_post(self):
        models.SubscribedFeedUserMapping.objects.filter(user=FeedTestCase.user).delete()

        c = Client()
        response = c.post('/api/feed/subscribe?url=http://www.feedforall.com/sample.xml', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feed_subscribe_post_duplicate(self):
        feed = None
        try:
            feed = models.Feed.objects.get(feed_url='http://www.feedforall.com/sample.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://www.feedforall.com/sample.xml',
                is_new=False,
                title='FeedForAll Sample Feed',
                home_url='http://www.feedforall.com/industry-solutions.htm',
                published_at=datetime.datetime.utcnow(),
                updated_at=None)
            feed.save()

        subscribed_feed_user_mapping = None
        try:
            subscribed_feed_user_mapping = models.SubscribedFeedUserMapping.objects.get(user=FeedTestCase.user, feed=feed)
        except models.SubscribedFeedUserMapping.DoesNotExist:
            subscribed_feed_user_mapping = models.SubscribedFeedUserMapping(
                feed=feed,
                user=FeedTestCase.user)
            subscribed_feed_user_mapping.save()

        c = Client()
        response = c.post('/api/feed/subscribe?url=http://www.feedforall.com/sample.xml', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 409)

    def test_feed_subscribe_post_no_url(self):
        c = Client()
        response = c.post('/api/feed/subscribe', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_feed_subscribe_post_non_rss_url(self):
        c = Client()
        response = c.post('/api/feed/subscribe?url=http://www.feedforall.com/bad.xml', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feed_subscribe_delete(self):
        feed = None
        try:
            feed = models.Feed.objects.get(feed_url='http://www.feedforall.com/sample.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://www.feedforall.com/sample.xml',
                is_new=False,
                title='FeedForAll Sample Feed',
                home_url='http://www.feedforall.com/industry-solutions.htm',
                published_at=datetime.datetime.utcnow(),
                updated_at=None)
            feed.save()

        subscribed_feed_user_mapping = None
        try:
            subscribed_feed_user_mapping = models.SubscribedFeedUserMapping.objects.get(user=FeedTestCase.user, feed=feed)
        except models.SubscribedFeedUserMapping.DoesNotExist:
            subscribed_feed_user_mapping = models.SubscribedFeedUserMapping(
                feed=feed,
                user=FeedTestCase.user)
            subscribed_feed_user_mapping.save()

        c = Client()
        response = c.delete('/api/feed/subscribe?url=http://www.feedforall.com/sample.xml', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feed_subscribe_delete_not_subscribed(self):
        c = Client()
        response = c.delete('/api/feed/subscribe?url=http://www.feedforall.com/bad.xml', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feed_subscribe_delete_no_url(self):
        c = Client()
        response = c.delete('/api/feed/subscribe', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)
