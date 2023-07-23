import logging
import uuid
from typing import ClassVar

from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import Feed, User, UserCategory


class UserCategoryTestCase(APITestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]
    user: ClassVar[User]

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

        cls.user = User.objects.create_user("test@test.com", None)

    def setUp(self):
        super().setUp()

        self.client.force_authenticate(user=UserCategoryTestCase.user)

    def test_UserCategoryView_get(self):
        user_category = UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.get(
            f"/api/usercategory/{user_category.uuid}",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_UserCategoryView_get_not_found(self):
        response = self.client.get(
            f"/api/usercategory/{uuid.uuid4()}",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_UserCategoryCreateView_post(self):
        response = self.client.post(
            "/api/usercategory",
            {
                "text": "test_usercategory_post",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_UserCategoryCreateView_post_malformed(self):
        response = self.client.post(
            "/api/usercategory",
            {},
        )
        self.assertEqual(response.status_code, 400, response.content)

        response = self.client.post(
            "/api/usercategory",
            {
                "text": 0,
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_UserCategoryCreateView_post_already_exists(self):
        UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.post(
            "/api/usercategory",
            {
                "text": "Test User Category",
            },
        )
        self.assertEqual(response.status_code, 409, response.content)

    def test_UserCategoryView_put(self):
        user_category = UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.put(
            f"/api/usercategory/{user_category.uuid}",
            {
                "text": "Test User Category 2",
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_UserCategoryView_put_malformed(self):
        user_category = UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.put(
            f"/api/usercategory/{user_category.uuid}",
            {
                "text": 0,
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_UserCategoryView_put_not_found(self):
        response = self.client.put(
            f"/api/usercategory/{uuid.uuid4()}",
            {
                "text": "Does not matter :)",
            },
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_UserCategoryView_put_already_exists(self):
        UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Already Exists Text"
        )

        user_category = UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.put(
            f"/api/usercategory/{user_category.uuid}",
            {
                "text": "Already Exists Text",
            },
        )
        self.assertEqual(response.status_code, 409, response.content)

    def test_UserCategoryView_delete(self):
        user_category = UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.delete(
            f"/api/usercategory/{user_category.uuid}",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_UserCategoryView_delete_not_found(self):
        response = self.client.delete(
            f"/api/usercategory/{uuid.uuid4()}",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_UserCategoriesQueryView_post(self):
        UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.post(
            "/api/usercategories/query",
            {},
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_UserCategoriesApplyView_put(self):
        feed1 = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url="http://example.com/rss2.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        user_category1 = UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category 1"
        )
        user_category2 = UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category 2"
        )

        response = self.client.put(
            "/api/usercategories/apply",
            {
                str(feed1.uuid): [str(user_category1.uuid)],
                str(feed2.uuid): [
                    str(user_category1.uuid),
                    str(user_category2.uuid),
                ],
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertIsNotNone(user_category1.feeds.get(uuid=feed1.uuid))
        self.assertIsNotNone(user_category2.feeds.get(uuid=feed2.uuid))
        self.assertIsNotNone(user_category2.feeds.get(uuid=feed2.uuid))

        user_category1.feeds.remove(feed1, feed2)
        user_category2.feeds.remove(feed1, feed2)

        response = self.client.put(
            "/api/usercategories/apply",
            {
                str(feed1.uuid): [str(user_category1.uuid)],
                str(feed2.uuid): [
                    str(user_category1.uuid),
                    str(user_category2.uuid),
                    str(user_category1.uuid),
                ],
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertIsNotNone(user_category1.feeds.get(uuid=feed1.uuid))
        self.assertIsNotNone(user_category1.feeds.get(uuid=feed2.uuid))
        self.assertIsNotNone(user_category2.feeds.get(uuid=feed2.uuid))

    def test_UserCategoriesApplyView_put_malformed(self):
        UserCategory.objects.create(
            user=UserCategoryTestCase.user, text="Test User Category"
        )

        response = self.client.put(
            "/api/usercategories/apply",
            {
                "test": [],
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

        response = self.client.put(
            "/api/usercategories/apply",
            {
                str(uuid.uuid4()): "test",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

        response = self.client.put(
            "/api/usercategories/apply",
            {
                str(uuid.uuid4()): ["test"],
            },
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_UserCategoriesApplyView_put_not_found(self):
        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        response = self.client.put(
            "/api/usercategories/apply",
            {
                str(uuid.uuid4()): [],
            },
        )
        self.assertEqual(response.status_code, 404, response.content)

        response = self.client.put(
            "/api/usercategories/apply",
            {
                str(feed.uuid): [str(uuid.uuid4())],
            },
        )
        self.assertEqual(response.status_code, 404, response.content)
