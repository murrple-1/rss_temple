import logging
from typing import ClassVar

from django.test import tag
from django.utils import timezone

from api import fields
from api.models import Feed, SubscribedFeedUserMapping, User
from api.tests import TestFileServerTestCase


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

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    def generate_credentials(self):
        user = User.objects.create_user("test@test.com", None)
        self.client.force_authenticate(user=user)

        return user

    @tag("slow")
    def test_feed_get(self):
        self.generate_credentials()

        response = self.client.get(
            "/api/feed",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
                "fields": ",".join(fields.field_list("feed")),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_feed_get_no_url(self):
        self.generate_credentials()

        response = self.client.get("/api/feed")
        self.assertEqual(response.status_code, 400, response.content)

    @tag("slow")
    def test_feed_get_non_rss_url(self):
        self.generate_credentials()

        response = self.client.get(
            "/api/feed",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/sample-404.xml",
            },
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feeds_query_post(self):
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

    @tag("slow")
    def test_feed_subscribe_post(self):
        self.generate_credentials()

        response = self.client.post(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feed_subscribe_post_duplicate(self):
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
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
        )
        self.assertEqual(response.status_code, 409, response.content)

    @tag("slow")
    def test_feed_subscribe_post_existing_custom_title(self):
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
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0_ns/well_formed.xml&customtitle=Custom%20Title",
        )
        self.assertEqual(response.status_code, 409, response.content)

    def test_feed_subscribe_post_no_url(self):
        self.generate_credentials()

        response = self.client.post("/api/feed/subscribe")
        self.assertEqual(response.status_code, 400, response.content)

    @tag("slow")
    def test_feed_subscribe_post_non_rss_url(self):
        self.generate_credentials()

        response = self.client.post(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/sample-404.xml",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feed_subscribe_put(self):
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
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml&customtitle=Custom%20Title%202",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            SubscribedFeedUserMapping.objects.filter(
                feed=feed, user=user, custom_feed_title="Custom Title 2"
            ).count(),
            1,
        )

    def test_feed_subscribe_put_no_url(self):
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
            "/api/feed/subscribe?customtitle=Custom%20Title%202",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"url", response.content)
        self.assertIn(b"missing", response.content)

    def test_feed_subscribe_put_not_subscribed(self):
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
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml&customtitle=Custom%20Title%202",
        )
        self.assertEqual(response.status_code, 404, response.content)
        self.assertIn(b"not subscribed", response.content)

    def test_feed_subscribe_put_renames(self):
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
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml&customtitle=Custom%20Title",
        )
        self.assertEqual(response.status_code, 204, response.content)

        response = self.client.put(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml&customtitle=Custom%20Title%202",
        )
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn(b"already used", response.content)

    def test_feed_subscribe_delete(self):
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
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feed_subscribe_delete_not_subscribed(self):
        self.generate_credentials()

        response = self.client.delete(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/sample-404.xml",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feed_subscribe_delete_no_url(self):
        self.generate_credentials()

        response = self.client.delete("/api/feed/subscribe")
        self.assertEqual(response.status_code, 400, response.content)
