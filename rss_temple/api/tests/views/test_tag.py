import logging
import datetime
import uuid

from django.test import TestCase, Client
from django.core.cache import caches

import ujson

from api import models


class TagTestCase(TestCase):
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

        cls.session = models.Session.objects.create(
            user=cls.user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))

        cls.session_token = cls.session.uuid
        cls.session_token_str = str(cls.session.uuid)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger('rss_temple').setLevel(cls.old_app_logger_level)
        logging.getLogger('django').setLevel(cls.old_django_logger_level)

    def test_tag_get(self):
        tag = models.Tag.objects.create(label_text='Test Tag')

        c = Client()

        response = c.get(f'/api/tag/{tag.uuid}',
                         HTTP_X_SESSION_TOKEN=TagTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_tag_get_not_found(self):
        c = Client()

        response = c.get(f'/api/tag/{uuid.uuid4()}',
                         HTTP_X_SESSION_TOKEN=TagTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_tags_query_post(self):
        models.Tag.objects.create(label_text='Test Tag')

        c = Client()

        response = c.post('/api/tags/query', '{}', 'application/json',
                          HTTP_X_SESSION_TOKEN=TagTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_tags_query_popular_post(self):
        cache = caches['tags']
        cache.delete('popular_uuids')

        models.Tag.objects.create(label_text='Test Tag 1')
        models.Tag.objects.create(label_text='Test Tag 2')
        models.Tag.objects.create(label_text='Test Tag 3')
        models.Tag.objects.create(label_text='Test Tag 4')

        c = Client()

        response = c.post('/api/tags/query/popular', '{}', 'application/json',
                          HTTP_X_SESSION_TOKEN=TagTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)
        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, dict)
        self.assertIn('objects', json_)
        self.assertIsInstance(json_['objects'], list)
        self.assertEqual(len(json_['objects']), 4)

    def test_tags_query_popular_post_withcache(self):
        cache = caches['tags']

        tag1 = models.Tag.objects.create(label_text='Test Tag 1')
        tag2 = models.Tag.objects.create(label_text='Test Tag 2')
        tag3 = models.Tag.objects.create(label_text='Test Tag 3')
        tag4 = models.Tag.objects.create(label_text='Test Tag 4')

        cache.set('popular_uuids', [tag1.uuid, tag3.uuid, tag2.uuid])

        c = Client()

        response = c.post('/api/tags/query/popular', ujson.dumps({
            'fields': ['uuid'],
        }), 'application/json',
                          HTTP_X_SESSION_TOKEN=TagTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)
        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, dict)
        self.assertIn('objects', json_)
        self.assertIsInstance(json_['objects'], list)
        self.assertEqual(len(json_['objects']), 3)
        self.assertEqual(json_['objects'][0]['uuid'], str(tag1.uuid))
        self.assertEqual(json_['objects'][1]['uuid'], str(tag3.uuid))
        self.assertEqual(json_['objects'][2]['uuid'], str(tag2.uuid))
