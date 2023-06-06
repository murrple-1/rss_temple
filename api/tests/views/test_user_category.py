import datetime
import logging
import uuid

import ujson
from django.utils import timezone

from api import models
from api.tests.views import ViewTestCase


class UserCategoryTestCase(ViewTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)
        logging.getLogger("django").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = models.User.objects.create(email="test@test.com")

        cls.session = models.Session.objects.create(
            user=cls.user,
            expires_at=timezone.now() + datetime.timedelta(days=2),
        )

        cls.session_token = cls.session.uuid
        cls.session_token_str = str(cls.session.uuid)

    def test_usercategory_get(self):
        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.get(
            f"/api/usercategory/{user_category.uuid}",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_usercategory_get_not_found(self):
        response = self.client.get(
            f"/api/usercategory/{uuid.uuid4()}",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_usercategory_post(self):
        response = self.client.post(
            "/api/usercategory",
            ujson.dumps(
                {
                    "text": "test_usercategory_post",
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_usercategory_post_malformed(self):
        response = self.client.post(
            "/api/usercategory",
            ujson.dumps({}),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 400, response.content)

        response = self.client.post(
            "/api/usercategory",
            ujson.dumps(
                {
                    "text": 0,
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_usercategory_post_already_exists(self):
        models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.post(
            "/api/usercategory",
            ujson.dumps(
                {
                    "text": "Test User Category",
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 409, response.content)

    def test_usercategory_put(self):
        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.put(
            f"/api/usercategory/{user_category.uuid}",
            ujson.dumps(
                {
                    "text": "Test User Category 2",
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_usercategory_put_malformed(self):
        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.put(
            f"/api/usercategory/{user_category.uuid}",
            ujson.dumps(
                {
                    "text": 0,
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_usercategory_put_not_found(self):
        response = self.client.put(
            f"/api/usercategory/{uuid.uuid4()}",
            ujson.dumps(
                {
                    "text": "Does not matter :)",
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_usercategory_put_already_exists(self):
        models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Already Exists Text"
        )

        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.put(
            f"/api/usercategory/{user_category.uuid}",
            ujson.dumps(
                {
                    "text": "Already Exists Text",
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 409, response.content)

    def test_usercategory_delete(self):
        user_category = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.delete(
            f"/api/usercategory/{user_category.uuid}",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_usercategory_delete_not_found(self):
        response = self.client.delete(
            f"/api/usercategory/{uuid.uuid4()}",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_usercategories_query_post(self):
        models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.post(
            "/api/usercategories/query",
            ujson.dumps({}),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_usercategories_apply_put(self):
        feed1 = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = models.Feed.objects.create(
            feed_url="http://example.com/rss2.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        user_category1 = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category 1"
        )
        user_category2 = models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category 2"
        )

        response = self.client.put(
            "/api/usercategories/apply",
            ujson.dumps(
                {
                    str(feed1.uuid): [str(user_category1.uuid)],
                    str(feed2.uuid): [
                        str(user_category1.uuid),
                        str(user_category2.uuid),
                    ],
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertIsNotNone(
            models.FeedUserCategoryMapping.objects.get(
                user_category=user_category1, feed=feed1
            )
        )
        self.assertIsNotNone(
            models.FeedUserCategoryMapping.objects.get(
                user_category=user_category1, feed=feed2
            )
        )
        self.assertIsNotNone(
            models.FeedUserCategoryMapping.objects.get(
                user_category=user_category2, feed=feed2
            )
        )

        models.FeedUserCategoryMapping.objects.filter(
            user_category__in=[user_category1, user_category2], feed__in=[feed1, feed2]
        ).delete()

        response = self.client.put(
            "/api/usercategories/apply",
            ujson.dumps(
                {
                    str(feed1.uuid): [str(user_category1.uuid)],
                    str(feed2.uuid): [
                        str(user_category1.uuid),
                        str(user_category2.uuid),
                        str(user_category1.uuid),
                    ],
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertIsNotNone(
            models.FeedUserCategoryMapping.objects.get(
                user_category=user_category1, feed=feed1
            )
        )
        self.assertIsNotNone(
            models.FeedUserCategoryMapping.objects.get(
                user_category=user_category1, feed=feed2
            )
        )
        self.assertIsNotNone(
            models.FeedUserCategoryMapping.objects.get(
                user_category=user_category2, feed=feed2
            )
        )

    def test_usercategories_apply_put_malformed(self):
        models.UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.put(
            "/api/usercategories/apply",
            ujson.dumps(
                {
                    "test": [],
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 400, response.content)

        response = self.client.put(
            "/api/usercategories/apply",
            ujson.dumps(
                {
                    str(uuid.uuid4()): "test",
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 400, response.content)

        response = self.client.put(
            "/api/usercategories/apply",
            ujson.dumps(
                {
                    str(uuid.uuid4()): ["test"],
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_usercategories_apply_put_not_found(self):
        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        response = self.client.put(
            "/api/usercategories/apply",
            ujson.dumps(
                {
                    str(uuid.uuid4()): [],
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 404, response.content)

        response = self.client.put(
            "/api/usercategories/apply",
            ujson.dumps(
                {
                    str(feed.uuid): [str(uuid.uuid4())],
                }
            ),
            "application/json",
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str,
        )
        self.assertEqual(response.status_code, 404, response.content)
