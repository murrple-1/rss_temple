import logging
import datetime
import uuid

from django.test import TestCase, Client

import ujson

from api import models


class UserCategoryTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

        try:
            cls.user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            cls.user = models.User(email='test@test.com')
            cls.user.save()

        session = models.Session(
            user=cls.user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))
        session.save()

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

    def test_usercategory_get(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        response = c.get('/api/usercategory/{}'.format(str(user_category.uuid)),
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_get_malformed_uuid(self):
        c = Client()

        response = c.get('/api/usercategory',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_usercategory_get_not_found(self):
        c = Client()

        response = c.get('/api/usercategory/{}'.format(str(uuid.uuid4())),
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_usercategory_post(self):
        c = Client()

        data = {
            'text': 'test_usercategory_post',
        }

        response = c.post('/api/usercategory',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_post_malformed(self):
        c = Client()

        data = {}

        response = c.post('/api/usercategory',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        data = {
            'text': 0,
        }

        response = c.post('/api/usercategory',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_usercategory_post_already_exists(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        data = {
            'text': 'Test User Category',
        }

        response = c.post('/api/usercategory',
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 409)

    def test_usercategory_put(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        data = {
            'text': 'Test User Category 2',
        }

        response = c.put('/api/usercategory/{}'.format(str(user_category.uuid)),
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_put_malformed(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        data = {
            'text': 'Does not matter :)',
        }

        response = c.put('/api/usercategory',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        data = {
            'text': 0,
        }

        response = c.put('/api/usercategory/{}'.format(str(user_category.uuid)),
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_usercategory_put_not_found(self):
        c = Client()

        data = {
            'text': 'Does not matter :)',
        }

        response = c.put('/api/usercategory/{}'.format(str(uuid.uuid4())),
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_usercategory_put_already_exists(self):
        if not models.UserCategory.objects.filter(user=UserCategoryTestCase.user, text='Already Exists Text'):
            models.UserCategory.objects.create(
                user=UserCategoryTestCase.user, text='Already Exists Text')

        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        data = {
            'text': 'Already Exists Text',
        }

        response = c.put('/api/usercategory/{}'.format(str(user_category.uuid)),
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 409)

    def test_usercategory_delete(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        response = c.delete('/api/usercategory/{}'.format(str(user_category.uuid)),
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_delete_malformed_uuid(self):
        c = Client()

        response = c.delete('/api/usercategory',
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_usercategory_delete_not_found(self):
        c = Client()

        response = c.delete('/api/usercategory/{}'.format(str(uuid.uuid4())),
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_usercategories_query_get(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        response = c.post('/api/usercategories/query', '{}', 'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_feed_post(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        feed1 = None
        try:
            feed1 = models.Feed.objects.get(
                feed_url='http://example.com/rss.xml')
        except models.Feed.DoesNotExist:
            feed1 = models.Feed(
                feed_url='http://example.com/rss.xml',
                title='Sample Feed',
                home_url='http://example.com',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed1.save()

        feed2 = None
        try:
            feed2 = models.Feed.objects.get(
                feed_url='http://example.com/rss2.xml')
        except models.Feed.DoesNotExist:
            feed2 = models.Feed(
                feed_url='http://example.com/rss2.xml',
                title='Sample Feed',
                home_url='http://example.com',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed2.save()

        models.FeedUserCategoryMapping.objects.filter(
            user_category=user_category, feed__in=[feed1, feed2]).delete()

        c = Client()

        data = [str(feed1.uuid), str(feed2.uuid)]

        response = c.post('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(
            user_category=user_category, feed=feed1))
        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(
            user_category=user_category, feed=feed2))

    def test_usercategory_feed_post_malformed(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        data = ['bad-uuid']

        response = c.post('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        data = 'bad-uuid'

        response = c.post('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        data = {
            'test': 'test',
        }

        response = c.post('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_usercategory_feed_post_not_found(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        data = []

        response = c.post('/api/usercategory/{}/feeds'.format(str(uuid.uuid4())),
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

        data = [
            str(uuid.uuid4()),
        ]

        response = c.post('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_usercategory_feed_post_already_exists(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        feed = None
        try:
            feed = models.Feed.objects.get(
                feed_url='http://example.com/rss.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://example.com/rss.xml',
                title='Sample Feed',
                home_url='http://example.com',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed.save()

        if not models.FeedUserCategoryMapping.objects.filter(feed=feed, user_category=user_category).exists():
            models.FeedUserCategoryMapping.objects.create(
                feed=feed, user_category=user_category)

        c = Client()

        data = [
            str(feed.uuid),
        ]

        response = c.post('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                          ujson.dumps(data),
                          'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 409)

    def test_usercategory_feed_delete(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        feed1 = None
        try:
            feed1 = models.Feed.objects.get(
                feed_url='http://example.com/rss.xml')
        except models.Feed.DoesNotExist:
            feed1 = models.Feed(
                feed_url='http://example.com/rss.xml',
                title='Sample Feed',
                home_url='http://example.com',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed1.save()

        feed2 = None
        try:
            feed2 = models.Feed.objects.get(
                feed_url='http://example.com/rss2.xml')
        except models.Feed.DoesNotExist:
            feed2 = models.Feed(
                feed_url='http://example.com/rss2.xml',
                title='Sample Feed',
                home_url='http://example.com',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed1.save()

        if not models.FeedUserCategoryMapping.objects.filter(user_category=user_category, feed=feed1).exists():
            models.FeedUserCategoryMapping.objects.create(
                user_category=user_category, feed=feed1)

        if not models.FeedUserCategoryMapping.objects.filter(user_category=user_category, feed=feed2).exists():
            models.FeedUserCategoryMapping.objects.create(
                user_category=user_category, feed=feed2)

        c = Client()

        data = [str(feed1.uuid), str(feed2.uuid)]

        response = c.delete('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        with self.assertRaises(models.FeedUserCategoryMapping.DoesNotExist):
            models.FeedUserCategoryMapping.objects.get(
                user_category=user_category, feed=feed1)

        with self.assertRaises(models.FeedUserCategoryMapping.DoesNotExist):
            models.FeedUserCategoryMapping.objects.get(
                user_category=user_category, feed=feed2)

    def test_usercategory_feed_delete_malformed(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        data = ['bad-uuid']

        response = c.delete('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        data = 'bad-uuid'

        response = c.delete('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        data = {
            'test': 'test',
        }

        response = c.delete('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_usercategory_feed_delete_not_found(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        data = []

        response = c.delete('/api/usercategory/{}/feeds'.format(str(uuid.uuid4())),
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

        data = [
            str(uuid.uuid4()),
        ]

        response = c.delete('/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
                            ujson.dumps(data),
                            'application/json',
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)
