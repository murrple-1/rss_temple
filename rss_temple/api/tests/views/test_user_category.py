import logging
import datetime

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
            user_category = models.UserCategory.objects.get(user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        response = c.get('/api/usercategory/{}'.format(str(user_category.uuid)),
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_post(self):
        c = Client()

        data = {
            'text': 'test_usercategory_post',
        }

        response = c.post('/api/usercategory', data,
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_put(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        data = {
            'text': 'Test User Category 2',
        }

        response = c.put('/api/usercategory/{}'.format(str(user_category.uuid)), data,
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_delete(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        response = c.delete('/api/usercategory/{}'.format(str(user_category.uuid)),
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategories_get(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        response = c.get('/api/usercategories',
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_usercategory_feed_post(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(user=UserCategoryTestCase.user, text='Test User Category')
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

        models.FeedUserCategoryMapping.objects.filter(user_category=user_category, feed__in=[feed1, feed2]).delete()

        c = Client()

        data = [str(feed1.uuid), str(feed2.uuid)]

        response = c.post(
            '/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
            ujson.dumps(data),
            'application/json',
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200, response.content)

        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(user_category=user_category, feed=feed1))
        self.assertIsNotNone(models.FeedUserCategoryMapping.objects.get(user_category=user_category, feed=feed2))

    def test_usercategory_feed_delete(self):
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(user=UserCategoryTestCase.user, text='Test User Category')
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

        response = c.delete(
            '/api/usercategory/{}/feeds'.format(str(user_category.uuid)),
            ujson.dumps(data),
            'application/json',
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200, response.content)

        with self.assertRaises(models.FeedUserCategoryMapping.DoesNotExist):
            models.FeedUserCategoryMapping.objects.get(user_category=user_category, feed=feed1)

        with self.assertRaises(models.FeedUserCategoryMapping.DoesNotExist):
            models.FeedUserCategoryMapping.objects.get(user_category=user_category, feed=feed2)
