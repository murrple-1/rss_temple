import datetime
import logging
import time
from multiprocessing import Process

from django.test import TestCase, Client

import ujson

from api import models, fields


def _http_server_process():
    import os
    import sys
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    sys.stdout = open('/dev/null', 'w')
    sys.stderr = sys.stdout

    os.chdir('api/tests/test_files/')

    with HTTPServer(('', 8080), SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()


class FeedTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

        user = None
        try:
            user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User(email='test@test.com')
            user.save()

        cls.user = user

        session = models.Session(
            user=user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))
        session.save()

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

        cls.http_process = Process(target=_http_server_process)
        cls.http_process.start()

        time.sleep(2.0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        cls.http_process.terminate()

        time.sleep(2.0)

    def test_feed_get(self):
        c = Client()
        response = c.get('/api/feed', {
            'url': 'http://localhost:8080/rss_2.0/well_formed.xml',
            'fields': ','.join(fields.field_list('feed')),
        }, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feed_get_no_url(self):
        c = Client()
        response = c.get(
            '/api/feed', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_feed_get_non_rss_url(self):
        c = Client()
        response = c.get('/api/feed', {
            'url': 'http://localhost:8080/rss_2.0/sample-404.xml',
        }, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feeds_get(self):
        feed = None
        try:
            feed = models.Feed.objects.get(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed.save()

        c = Client()
        response = c.get('/api/feeds', {'fields': ','.join(fields.field_list(
            'feed'))}, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        _json = ujson.loads(response.content)

        self.assertIsInstance(_json, dict)
        self.assertIn('objects', _json)
        self.assertIsInstance(_json['objects'], list)
        self.assertGreaterEqual(len(_json['objects']), 1)

    def test_feed_subscribe_post(self):
        models.SubscribedFeedUserMapping.objects.filter(
            user=FeedTestCase.user).delete()

        c = Client()
        response = c.post('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feed_subscribe_post_duplicate(self):
        feed = None
        try:
            feed = models.Feed.objects.get(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed.save()

        subscribed_feed_user_mapping = None
        try:
            subscribed_feed_user_mapping = models.SubscribedFeedUserMapping.objects.get(
                user=FeedTestCase.user, feed=feed)
        except models.SubscribedFeedUserMapping.DoesNotExist:
            subscribed_feed_user_mapping = models.SubscribedFeedUserMapping(
                feed=feed,
                user=FeedTestCase.user)
            subscribed_feed_user_mapping.save()

        c = Client()
        response = c.post('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 409)

    def test_feed_subscribe_post_existing_custom_title(self):
        feed = None
        try:
            feed = models.Feed.objects.get(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed.save()

        models.SubscribedFeedUserMapping.objects.filter(user=FeedTestCase.user).delete()
        subscribed_feed_user_mapping = models.SubscribedFeedUserMapping.objects.create(
            feed=feed,
            user=FeedTestCase.user,
            custom_feed_title='Custom Title')

        c = Client()
        response = c.post('/api/feed/subscribe?url=http://localhost:8080/rss_2.0_ns/well_formed.xml&customtitle=Custom%20Title',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 409)

    def test_feed_subscribe_post_no_url(self):
        c = Client()
        response = c.post('/api/feed/subscribe',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_feed_subscribe_post_non_rss_url(self):
        c = Client()
        response = c.post('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/sample-404.xml',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feed_subscribe_delete(self):
        feed = None
        try:
            feed = models.Feed.objects.get(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed.save()

        subscribed_feed_user_mapping = None
        try:
            subscribed_feed_user_mapping = models.SubscribedFeedUserMapping.objects.get(
                user=FeedTestCase.user, feed=feed)
        except models.SubscribedFeedUserMapping.DoesNotExist:
            subscribed_feed_user_mapping = models.SubscribedFeedUserMapping(
                feed=feed,
                user=FeedTestCase.user)
            subscribed_feed_user_mapping.save()

        c = Client()
        response = c.delete('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml',
                            HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feed_subscribe_delete_not_subscribed(self):
        c = Client()
        response = c.delete('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/sample-404.xml',
                            HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feed_subscribe_delete_no_url(self):
        c = Client()
        response = c.delete('/api/feed/subscribe',
                            HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)
