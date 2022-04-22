import logging
from urllib.parse import quote

import ujson
from django.test import modify_settings, tag
from django.utils import timezone

from api.models import User, Feed, SubscribedFeedUserMapping
from api.tests import TestFileServerTestCase


def _encode_url(url):
    return quote(quote(url, safe=""))


@tag("views")
@modify_settings(
    MIDDLEWARE={
        "remove": ["api.middleware.throttle.ThrottleMiddleware"],
    }
)
class FeedTestCase(TestFileServerTestCase):
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

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_user("test@test.com", "password")

        self.client.login(email="test@test.com", password="password")

    @tag("slow")
    def test_feeds_url_get(self):
        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"
        )

        response = self.client.get(
            f"/api/feeds/{url_encoded}",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)

        self.assertIs(type(json_), dict)

    @tag("slow")
    def test_feeds_url_get_non_rss_url(self):
        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/sample-404.xml"
        )

        response = self.client.get(
            f"/api/feeds/{url_encoded}",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feeds_get(self):
        Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        response = self.client.get(
            "/api/feeds",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)

        self.assertIs(type(json_), dict)

    @tag("slow")
    def test_feeds_subscribe_post(self):
        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"
        )

        response = self.client.post(
            f"/api/feeds/subscribe/{url_encoded}",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feeds_subscribe_post_duplicate(self):
        feed = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(feed=feed, user=self.user)

        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"
        )

        response = self.client.post(
            f"/api/feeds/subscribe/{url_encoded}",
        )
        self.assertEqual(response.status_code, 409, response.content)

    @tag("slow")
    def test_feeds_subscribe_post_existing_custom_title(self):
        feed = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(
            feed=feed, user=self.user, custom_feed_title="Custom Title"
        )

        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_1.0/well_formed.xml"
        )

        response = self.client.post(
            f"/api/feeds/subscribe/{url_encoded}?customtitle=Custom%20Title",
        )
        self.assertEqual(response.status_code, 409, response.content)

    @tag("slow")
    def test_feeds_subscribe_post_non_rss_url(self):
        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/sample-404.xml"
        )

        response = self.client.post(
            f"/api/feeds/subscribe/{url_encoded}",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feeds_subscribe_put(self):
        feed = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(
            feed=feed, user=self.user, custom_feed_title="Custom Title"
        )

        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"
        )

        response = self.client.put(
            f"/api/feeds/subscribe/{url_encoded}?customtitle=Custom%20Title%202",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            SubscribedFeedUserMapping.objects.filter(
                feed=feed, user=self.user, custom_feed_title="Custom Title 2"
            ).count(),
            1,
        )

    def test_feeds_subscribe_put_not_subscribed(self):
        Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"
        )

        response = self.client.put(
            f"/api/feeds/subscribe/{url_encoded}?customtitle=Custom%20Title%202",
        )
        self.assertEqual(response.status_code, 404, response.content)
        self.assertIn(b"not subscribed", response.content)

    def test_feeds_subscribe_put_renames(self):
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
            feed=feed1, user=self.user, custom_feed_title="Custom Title"
        )

        SubscribedFeedUserMapping.objects.create(
            feed=feed2, user=self.user, custom_feed_title="Custom Title 2"
        )

        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"
        )

        response = self.client.put(
            f"/api/feeds/subscribe/{url_encoded}?customtitle=Custom%20Title",
        )
        self.assertEqual(response.status_code, 204, response.content)

        response = self.client.put(
            f"/api/feeds/subscribe/{url_encoded}?customtitle=Custom%20Title%202",
        )
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn(b"already used", response.content)

    def test_feeds_subscribe_delete(self):
        feed = Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(feed=feed, user=self.user)

        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml"
        )

        response = self.client.delete(
            f"/api/feeds/subscribe/{url_encoded}",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feeds_subscribe_delete_not_subscribed(self):
        url_encoded = _encode_url(
            f"{FeedTestCase.live_server_url}/rss_2.0/sample-404.xml"
        )

        response = self.client.delete(
            f"/api/feeds/subscribe/{url_encoded}",
        )
        self.assertEqual(response.status_code, 404, response.content)
