import logging
from typing import ClassVar

from django.core.cache import BaseCache, caches
from django.test import tag
from django.utils import timezone

from api import fields
from api.models import Feed, SubscribedFeedUserMapping, User
from api.tests import TestFileServerTestCase
from api.tests.utils import db_migrations_state, throttling_monkey_patch


class FeedTestCase(TestFileServerTestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)
        logging.getLogger("django").setLevel(logging.CRITICAL)

        throttling_monkey_patch()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    def setUp(self):
        super().setUp()

        db_migrations_state()

    def generate_credentials(self):
        user = User.objects.create_user("test@test.com", None)
        self.client.force_authenticate(user=user)

        return user

    @tag("slow")
    def test_FeedView_get(self):
        self.generate_credentials()

        response = self.client.get(
            "/api/feed",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
                "fields": fields.field_list("feed"),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_FeedView_get_no_url(self):
        self.generate_credentials()

        response = self.client.get("/api/feed")
        self.assertEqual(response.status_code, 400, response.content)

    @tag("slow")
    def test_FeedView_get_non_rss_url(self):
        self.generate_credentials()

        response = self.client.get(
            "/api/feed",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/sample-404.xml",
            },
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_FeedsQueryView_post(self):
        self.generate_credentials()

        Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        response = self.client.post(
            "/api/feeds/query",
            {"fields": list(fields.field_list("feed"))},
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), dict)
        self.assertIn("objects", json_)
        self.assertIs(type(json_["objects"]), list)
        self.assertGreaterEqual(len(json_["objects"]), 1)

    def test_FeedLookupView_get(self):
        cache: BaseCache = caches["captcha"]

        url = f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"

        cache_key = f"exposed_feeds_{url}"
        self.assertFalse(cache.delete(cache_key))

        self.generate_credentials()

        response = self.client.get(
            "/api/feed/lookup",
            {"url": url},
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), list)
        self.assertEqual(len(json_), 1)
        self.assertEqual(response.headers["X-Cache-Hit"], "NO")

        response = self.client.get(
            "/api/feed/lookup",
            {"url": url},
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), list)
        self.assertEqual(len(json_), 1)
        self.assertEqual(response.headers["X-Cache-Hit"], "YES")

    @tag("slow")
    def test_FeedSubscribeView_post(self):
        self.generate_credentials()

        response = self.client.post(
            "/api/feed/subscribe",
            {"url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"},
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_FeedSubscribeView_post_duplicate(self):
        user = self.generate_credentials()

        feed = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(feed=feed, user=user)

        response = self.client.post(
            "/api/feed/subscribe",
            {"url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"},
        )
        self.assertEqual(response.status_code, 409, response.content)

    @tag("slow")
    def test_FeedSubscribeView_post_existing_custom_title(self):
        user = self.generate_credentials()

        feed = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(
            feed=feed, user=user, custom_feed_title="Custom Title"
        )

        response = self.client.post(
            "/api/feed/subscribe",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0_ns/well_formed.xml",
                "customTitle": "Custom Title",
            },
        )
        self.assertEqual(response.status_code, 409, response.content)

    def test_FeedSubscribeView_post_no_url(self):
        self.generate_credentials()

        response = self.client.post("/api/feed/subscribe")
        self.assertEqual(response.status_code, 400, response.content)

    @tag("slow")
    def test_FeedSubscribeView_post_non_rss_url(self):
        self.generate_credentials()

        response = self.client.post(
            "/api/feed/subscribe?url=",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/sample-404.xml",
            },
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_FeedSubscribeView_put(self):
        user = self.generate_credentials()

        feed = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(
            feed=feed, user=user, custom_feed_title="Custom Title"
        )

        response = self.client.put(
            "/api/feed/subscribe",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
                "customTitle": "Custom Title 2",
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            SubscribedFeedUserMapping.objects.filter(
                feed=feed, user=user, custom_feed_title="Custom Title 2"
            ).count(),
            1,
        )

    def test_FeedSubscribeView_put_no_url(self):
        user = self.generate_credentials()

        feed = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(
            feed=feed, user=user, custom_feed_title="Custom Title"
        )

        response = self.client.put(
            "/api/feed/subscribe",
            {
                "customTitle": "Custom Title 2",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"url", response.content)
        self.assertIn(b"required", response.content)

    def test_FeedSubscribeView_put_not_subscribed(self):
        self.generate_credentials()

        Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        response = self.client.put(
            "/api/feed/subscribe",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
                "customTitle": "Custom Title 2",
            },
        )
        self.assertEqual(response.status_code, 404, response.content)
        self.assertIn(b"not subscribed", response.content)

    def test_FeedSubscribeView_put_renames(self):
        user = self.generate_credentials()

        feed1 = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed2.xml",
            title="Sample Feed 2",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(
            feed=feed1, user=user, custom_feed_title="Custom Title"
        )

        SubscribedFeedUserMapping.objects.create(
            feed=feed2, user=user, custom_feed_title="Custom Title 2"
        )

        response = self.client.put(
            "/api/feed/subscribe",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
                "customTitle": "Custom Title",
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

        response = self.client.put(
            "/api/feed/subscribe",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
                "customTitle": "Custom Title 2",
            },
        )
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn(b"already used", response.content)

    def test_FeedSubscribeView_delete(self):
        user = self.generate_credentials()

        feed = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(feed=feed, user=user)

        response = self.client.delete(
            "/api/feed/subscribe",
            {"url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"},
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_FeedSubscribeView_delete_not_subscribed(self):
        self.generate_credentials()

        response = self.client.delete(
            "/api/feed/subscribe",
            {"url": f"{FeedTestCase.live_server_url}/rss_2.0/sample-404.xml"},
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_FeedSubscribeView_delete_no_url(self):
        self.generate_credentials()

        response = self.client.delete("/api/feed/subscribe")
        self.assertEqual(response.status_code, 400, response.content)
