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
            user = models.User.objects.create(email='test@test.com')

        cls.user = user

        session = models.Session.objects.create(
            user=user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))

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

    def test_feeds_query_post(self):
        if not models.Feed.objects.filter(feed_url='http://localhost:8080/rss_2.0/well_formed.xml').exists():
            models.Feed.objects.create(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)

        c = Client()
        response = c.post('/api/feeds/query', ujson.dumps({'fields': fields.field_list(
            'feed')}), 'application/json', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200, response.content)

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
            feed = models.Feed.objects.create(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)

        if not models.SubscribedFeedUserMapping.objects.filter(user=FeedTestCase.user, feed=feed).exists():
            models.SubscribedFeedUserMapping.objects.create(
                feed=feed,
                user=FeedTestCase.user)

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
            feed = models.Feed.objects.create(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)

        models.SubscribedFeedUserMapping.objects.filter(
            user=FeedTestCase.user).delete()
        models.SubscribedFeedUserMapping.objects.create(
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
            feed = models.Feed.objects.create(
                feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
                title='Sample Feed',
                home_url='http://localhost:8080',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)

        if not models.SubscribedFeedUserMapping.objects.filter(user=FeedTestCase.user, feed=feed).exists():
            models.SubscribedFeedUserMapping.objects.create(
                feed=feed,
                user=FeedTestCase.user)

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
