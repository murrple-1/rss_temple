import datetime
import logging
import time
from multiprocessing import Process

from django.test import TestCase, Client

import ujson

from api import models, fields
from api.tests.http_server import http_server_target


class FeedTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger(
            'rss_temple').getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger(
            'django').getEffectiveLevel()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

        cls.user = models.User.objects.create(email='test@test.com')

        session = models.Session.objects.create(
            user=cls.user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

        cls.http_process = Process(target=http_server_target, args=(8080,))
        cls.http_process.start()

        time.sleep(2.0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger('rss_temple').setLevel(cls.old_app_logger_level)
        logging.getLogger('django').setLevel(cls.old_django_logger_level)

        cls.http_process.terminate()

        time.sleep(2.0)

    def test_feed_get(self):
        c = Client()
        response = c.get('/api/feed', {
            'url': 'http://localhost:8080/rss_2.0/well_formed.xml',
            'fields': ','.join(fields.field_list('feed')),
        }, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200, response.content)

    def test_feed_get_no_url(self):
        c = Client()
        response = c.get(
            '/api/feed', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400, response.content)

    def test_feed_get_non_rss_url(self):
        c = Client()
        response = c.get('/api/feed', {
            'url': 'http://localhost:8080/rss_2.0/sample-404.xml',
        }, HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404, response.content)

    def test_feeds_query_post(self):
        models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        c = Client()
        response = c.post('/api/feeds/query', ujson.dumps({'fields': list(fields.field_list(
            'feed'))}), 'application/json', HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)

        self.assertIs(type(json_), dict)
        self.assertIn('objects', json_)
        self.assertIs(type(json_['objects']), list)
        self.assertGreaterEqual(len(json_['objects']), 1)

    def test_feed_subscribe_post(self):
        c = Client()
        response = c.post('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 204, response.content)

    def test_feed_subscribe_post_duplicate(self):
        feed = models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed,
            user=FeedTestCase.user)

        c = Client()
        response = c.post('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 409, response.content)

    def test_feed_subscribe_post_existing_custom_title(self):
        feed = models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed,
            user=FeedTestCase.user,
            custom_feed_title='Custom Title')

        c = Client()
        response = c.post('/api/feed/subscribe?url=http://localhost:8080/rss_2.0_ns/well_formed.xml&customtitle=Custom%20Title',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 409, response.content)

    def test_feed_subscribe_post_no_url(self):
        c = Client()
        response = c.post('/api/feed/subscribe',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400, response.content)

    def test_feed_subscribe_post_non_rss_url(self):
        c = Client()
        response = c.post('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/sample-404.xml',
                          HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404, response.content)

    def test_feed_subscribe_put(self):
        feed = models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed,
            user=FeedTestCase.user,
            custom_feed_title='Custom Title')

        c = Client()
        response = c.put('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml&customtitle=Custom%20Title%202',
                         HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(models.SubscribedFeedUserMapping.objects.filter(
            feed=feed, user=FeedTestCase.user, custom_feed_title='Custom Title 2').count(), 1)

    def test_feed_subscribe_put_no_url(self):
        feed = models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed,
            user=FeedTestCase.user,
            custom_feed_title='Custom Title')

        c = Client()
        response = c.put('/api/feed/subscribe?customtitle=Custom%20Title%202',
                         HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b'url', response.content)
        self.assertIn(b'missing', response.content)

    def test_feed_subscribe_put_not_subscribed(self):
        models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        c = Client()
        response = c.put('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml&customtitle=Custom%20Title%202',
                         HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404, response.content)
        self.assertIn(b'not subscribed', response.content)

    def test_feed_subscribe_put_renames(self):
        feed1 = models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed2 = models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed2.xml',
            title='Sample Feed 2',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed1,
            user=FeedTestCase.user,
            custom_feed_title='Custom Title')

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed2,
            user=FeedTestCase.user,
            custom_feed_title='Custom Title 2')

        c = Client()
        response = c.put('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml&customtitle=Custom%20Title',
                         HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 204, response.content)

        response = c.put('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml&customtitle=Custom%20Title%202',
                         HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn(b'already used', response.content)

    def test_feed_subscribe_delete(self):
        feed = models.Feed.objects.create(
            feed_url='http://localhost:8080/rss_2.0/well_formed.xml',
            title='Sample Feed',
            home_url='http://localhost:8080',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed,
            user=FeedTestCase.user)

        c = Client()
        response = c.delete('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/well_formed.xml',
                            HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 204, response.content)

    def test_feed_subscribe_delete_not_subscribed(self):
        c = Client()
        response = c.delete('/api/feed/subscribe?url=http://localhost:8080/rss_2.0/sample-404.xml',
                            HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 404, response.content)

    def test_feed_subscribe_delete_no_url(self):
        c = Client()
        response = c.delete('/api/feed/subscribe',
                            HTTP_X_SESSION_TOKEN=FeedTestCase.session_token_str)
        self.assertEqual(response.status_code, 400, response.content)
