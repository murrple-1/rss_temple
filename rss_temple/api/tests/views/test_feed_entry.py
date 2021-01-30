import logging
import datetime
import uuid

from django.test import TestCase, Client
from django.db import transaction

import ujson

from api import models


class FeedEntryTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger('rss_temple').getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger('django').getEffectiveLevel()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

        cls.user = models.User.objects.create(email='test@test.com')

        session = models.Session.objects.create(
            user=cls.user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

        cls.feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger('rss_temple').setLevel(cls.old_app_logger_level)
        logging.getLogger('django').setLevel(cls.old_django_logger_level)

    def test_feedentry_get(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        c = Client()

        response = c.get(f'/api/feedentry/{feed_entry.uuid}',
                         HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentry_get_not_found(self):
        c = Client()

        response = c.get(f'/api/feedentry/{uuid.uuid4()}',
                         HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feedentries_query_post(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        c = Client()

        response = c.post('/api/feedentries/query', '{}', 'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentry_read_post(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        c = Client()

        response = c.post(f'/api/feedentry/{feed_entry.uuid}/read',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertTrue(models.ReadFeedEntryUserMapping.objects.filter(
            user=FeedEntryTestCase.user, feed_entry=feed_entry).exists())

    def test_feedentry_read_post_not_found(self):
        c = Client()

        response = c.post(f'/api/feedentry/{uuid.uuid4()}/read',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feedentry_read_post_duplicate(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        models.ReadFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry)

        c = Client()

        with transaction.atomic():
            response = c.post(f'/api/feedentry/{feed_entry.uuid}/read',
                              HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
            self.assertEqual(response.status_code, 200)

        self.assertTrue(models.ReadFeedEntryUserMapping.objects.filter(
            user=FeedEntryTestCase.user, feed_entry=feed_entry).exists())

    def test_feedentry_read_delete(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        models.ReadFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry)

        c = Client()

        response = c.delete(f'/api/feedentry/{feed_entry.uuid}/read',
                            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(models.ReadFeedEntryUserMapping.objects.filter(
            user=FeedEntryTestCase.user, feed_entry=feed_entry).exists())

    def test_feedentries_read_post(self):
        feed_entry1 = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 1 Title',
            url='http://example.com/entry1.html',
            content='Some Entry content 1',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry1.save()

        feed_entry2 = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 2 Title',
            url='http://example.com/entry2.html',
            content='Some Entry content 2',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry2.save()

        c = Client()

        data = [str(feed_entry1.uuid), str(feed_entry2.uuid)]

        response = c.post('/api/feedentries/read',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(models.ReadFeedEntryUserMapping.objects.filter(
            user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]).count(), 2)

    def test_feedentries_read_post_shortcut(self):
        c = Client()

        data = []

        response = c.post('/api/feedentries/read',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentries_read_post_malformed(self):
        c = Client()

        data = [0]

        response = c.post('/api/feedentries/read',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_feedentries_read_post_not_found(self):
        c = Client()

        data = [str(uuid.uuid4())]

        response = c.post('/api/feedentries/read',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feedentries_read_post_duplicate(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        models.ReadFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry, user=FeedEntryTestCase.user)

        c = Client()

        data = [str(feed_entry.uuid)]

        response = c.post('/api/feedentries/read',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentries_read_delete(self):
        feed_entry1 = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 1 Title',
            url='http://example.com/entry1.html',
            content='Some Entry content 1',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry1.save()

        feed_entry2 = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 2 Title',
            url='http://example.com/entry2.html',
            content='Some Entry content 2',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry2.save()

        models.ReadFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry1)

        models.ReadFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry2)

        c = Client()

        data = [str(feed_entry1.uuid), str(feed_entry2.uuid)]

        response = c.delete('/api/feedentries/read',
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(models.ReadFeedEntryUserMapping.objects.filter(
            user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]).exists())

    def test_feedentries_read_delete_shortcut(self):
        c = Client()

        data = []

        response = c.delete('/api/feedentries/read',
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentries_read_delete_malformed(self):
        c = Client()

        data = [0]

        response = c.delete('/api/feedentries/read',
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_feedentry_favorite_post(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        c = Client()

        response = c.post(f'/api/feedentry/{feed_entry.uuid}/favorite',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertTrue(models.FavoriteFeedEntryUserMapping.objects.filter(
            user=FeedEntryTestCase.user, feed_entry=feed_entry).exists())

    def test_feedentry_favorite_post_not_found(self):
        c = Client()

        response = c.post(f'/api/feedentry/{uuid.uuid4()}/favorite',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feedentry_favorite_post_duplicate(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        models.FavoriteFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry, user=FeedEntryTestCase.user)

        c = Client()

        response = c.post(f'/api/feedentry/{feed_entry.uuid}/favorite',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentry_favorite_delete(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        models.FavoriteFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry)

        c = Client()

        response = c.delete(f'/api/feedentry/{feed_entry.uuid}/favorite',
                            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(models.FavoriteFeedEntryUserMapping.objects.filter(
            user=FeedEntryTestCase.user, feed_entry=feed_entry).exists())

    def test_feedentries_favorite_post(self):
        feed_entry1 = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 1 Title',
            url='http://example.com/entry1.html',
            content='Some Entry content 1',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry1.save()

        feed_entry2 = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 2 Title',
            url='http://example.com/entry2.html',
            content='Some Entry content 2',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry2.save()

        c = Client()

        data = [str(feed_entry1.uuid), str(feed_entry2.uuid)]

        response = c.post('/api/feedentries/favorite',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(models.FavoriteFeedEntryUserMapping.objects.filter(
            user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]).count(), 2)

    def test_feedentries_favorite_post_shortcut(self):
        c = Client()

        data = []

        response = c.post('/api/feedentries/favorite',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentries_favorite_post_malformed(self):
        c = Client()

        data = [0]

        response = c.post('/api/feedentries/favorite',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_feedentries_favorite_post_not_found(self):
        c = Client()

        data = [str(uuid.uuid4())]

        response = c.post('/api/feedentries/favorite',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_feedentries_favorite_post_duplicate(self):
        feed_entry = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry.save()

        models.FavoriteFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry, user=FeedEntryTestCase.user)

        c = Client()

        data = [str(feed_entry.uuid)]

        response = c.post('/api/feedentries/favorite',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentries_favorite_delete(self):
        feed_entry1 = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 1 Title',
            url='http://example.com/entry1.html',
            content='Some Entry content 1',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry1.save()

        feed_entry2 = models.FeedEntry(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 2 Title',
            url='http://example.com/entry2.html',
            content='Some Entry content 2',
            author_name='John Doe',
            db_updated_at=None)
        feed_entry2.save()

        models.FavoriteFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry1)

        models.FavoriteFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry2)

        c = Client()

        data = [str(feed_entry1.uuid), str(feed_entry2.uuid)]

        response = c.delete('/api/feedentries/favorite',
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(models.FavoriteFeedEntryUserMapping.objects.filter(
            user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]).exists())

    def test_feedentries_favorite_delete_shortcut(self):
        c = Client()

        data = []

        response = c.delete('/api/feedentries/favorite',
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentries_favorite_delete_malformed(self):
        c = Client()

        data = [0]

        response = c.delete('/api/feedentries/favorite',
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)
