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

        cls.old_app_logger_level = logging.getLogger('rss_temple').getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger('django').getEffectiveLevel()

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

    def test_usercategory_get(self):
        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category')

        c = Client()

        response = c.get(f'/api/usercategory/{user_category.uuid}',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_get_not_found(self):
        c = Client()

        response = c.get(f'/api/usercategory/{uuid.uuid4()}',
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
        models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category')

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
        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category')

        c = Client()

        data = {
            'text': 'Test User Category 2',
        }

        response = c.put(f'/api/usercategory/{user_category.uuid}',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_put_malformed(self):
        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category')

        c = Client()

        data = {
            'text': 0,
        }

        response = c.put(f'/api/usercategory/{user_category.uuid}',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_usercategory_put_not_found(self):
        c = Client()

        data = {
            'text': 'Does not matter :)',
        }

        response = c.put(f'/api/usercategory/{uuid.uuid4()}',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_usercategory_put_already_exists(self):
        models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Already Exists Text')

        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category')

        c = Client()

        data = {
            'text': 'Already Exists Text',
        }

        response = c.put(f'/api/usercategory/{user_category.uuid}',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 409)

    def test_usercategory_delete(self):
        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category')

        c = Client()

        response = c.delete(f'/api/usercategory/{user_category.uuid}',
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_delete_not_found(self):
        c = Client()

        response = c.delete(f'/api/usercategory/{uuid.uuid4()}',
                            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

    def test_usercategories_query_get(self):
        models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category')

        c = Client()

        response = c.post('/api/usercategories/query', '{}', 'application/json',
                          HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategories_apply_put(self):
        feed1 = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed2 = models.Feed.objects.create(
            feed_url='http://example.com/rss2.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        user_category1 = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category 1')
        user_category2 = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category 2')

        c = Client()

        data = {
            str(feed1.uuid): [str(user_category1.uuid)],
            str(feed2.uuid): [str(user_category1.uuid), str(user_category2.uuid)],
        }

        response = c.put('/api/usercategories/apply',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(
            user_category=user_category1, feed=feed1))
        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(
            user_category=user_category1, feed=feed2))
        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(
            user_category=user_category2, feed=feed2))

        models.FeedUserCategoryMapping.objects.filter(
            user_category__in=[user_category1, user_category2], feed__in=[feed1, feed2]).delete()

        data = {
            str(feed1.uuid): [str(user_category1.uuid)],
            str(feed2.uuid): [str(user_category1.uuid), str(user_category2.uuid), str(user_category1.uuid)],
        }

        response = c.put('/api/usercategories/apply',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(
            user_category=user_category1, feed=feed1))
        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(
            user_category=user_category1, feed=feed2))
        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(
            user_category=user_category2, feed=feed2))

    def test_usercategories_apply_put_malformed(self):
        models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text='Test User Category')

        c = Client()

        data = {
            'test': [],
        }

        response = c.put('/api/usercategories/apply',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        data = {
            str(uuid.uuid4()): 'test',
        }

        response = c.put('/api/usercategories/apply',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        data = {
            str(uuid.uuid4()): ['test'],
        }

        response = c.put('/api/usercategories/apply',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_usercategories_apply_put_not_found(self):
        feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        c = Client()

        data = {
            str(uuid.uuid4()): [],
        }

        response = c.put('/api/usercategories/apply',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)

        data = {
            str(feed.uuid): [str(uuid.uuid4())],
        }

        response = c.put('/api/usercategories/apply',
                         ujson.dumps(data),
                         'application/json',
                         HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 404)
