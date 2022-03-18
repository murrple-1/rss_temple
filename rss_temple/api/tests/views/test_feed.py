import datetime
import logging

import ujson
from api import fields, models
from api.tests import TestFileServerTestCase
from django.test import modify_settings, tag


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

    def generate_credentials(self):
        user = models.User.objects.create(email="test@test.com")

        session = models.Session.objects.create(
            user=user,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2),
        )

        return user, str(session.uuid)

    @tag("slow")
    def test_feed_get(self):
        user, session_token_str = self.generate_credentials()

        response = self.client.get(
            "/api/feed",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
                "fields": ",".join(fields.field_list("feed")),
            },
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_feed_get_no_url(self):
        user, session_token_str = self.generate_credentials()

        response = self.client.get("/api/feed", HTTP_X_SESSION_TOKEN=session_token_str)
        self.assertEqual(response.status_code, 400, response.content)

    @tag("slow")
    def test_feed_get_non_rss_url(self):
        user, session_token_str = self.generate_credentials()

        response = self.client.get(
            "/api/feed",
            {
                "url": f"{FeedTestCase.live_server_url}/rss_2.0/sample-404.xml",
            },
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feeds_query_post(self):
        user, session_token_str = self.generate_credentials()

        models.Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None,
        )

        response = self.client.post(
            "/api/feeds/query",
            ujson.dumps({"fields": list(fields.field_list("feed"))}),
            "application/json",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)

        self.assertIs(type(json_), dict)
        self.assertIn("objects", json_)
        self.assertIs(type(json_["objects"]), list)
        self.assertGreaterEqual(len(json_["objects"]), 1)

    @tag("slow")
    def test_feed_subscribe_post(self):
        user, session_token_str = self.generate_credentials()

        response = self.client.post(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feed_subscribe_post_duplicate(self):
        user, session_token_str = self.generate_credentials()

        feed = models.Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None,
        )

        models.SubscribedFeedUserMapping.objects.create(feed=feed, user=user)

        response = self.client.post(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 409, response.content)

    @tag("slow")
    def test_feed_subscribe_post_existing_custom_title(self):
        user, session_token_str = self.generate_credentials()

        feed = models.Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None,
        )

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed, user=user, custom_feed_title="Custom Title"
        )

        response = self.client.post(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0_ns/well_formed.xml&customtitle=Custom%20Title",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 409, response.content)

    def test_feed_subscribe_post_no_url(self):
        user, session_token_str = self.generate_credentials()

        response = self.client.post(
            "/api/feed/subscribe", HTTP_X_SESSION_TOKEN=session_token_str
        )
        self.assertEqual(response.status_code, 400, response.content)

    @tag("slow")
    def test_feed_subscribe_post_non_rss_url(self):
        user, session_token_str = self.generate_credentials()

        response = self.client.post(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/sample-404.xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feed_subscribe_put(self):
        user, session_token_str = self.generate_credentials()

        feed = models.Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None,
        )

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed, user=user, custom_feed_title="Custom Title"
        )

        response = self.client.put(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml&customtitle=Custom%20Title%202",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            models.SubscribedFeedUserMapping.objects.filter(
                feed=feed, user=user, custom_feed_title="Custom Title 2"
            ).count(),
            1,
        )

    def test_feed_subscribe_put_no_url(self):
        user, session_token_str = self.generate_credentials()

        feed = models.Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None,
        )

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed, user=user, custom_feed_title="Custom Title"
        )

        response = self.client.put(
            "/api/feed/subscribe?customtitle=Custom%20Title%202",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"url", response.content)
        self.assertIn(b"missing", response.content)

    def test_feed_subscribe_put_not_subscribed(self):
        user, session_token_str = self.generate_credentials()

        models.Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None,
        )

        response = self.client.put(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml&customtitle=Custom%20Title%202",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 404, response.content)
        self.assertIn(b"not subscribed", response.content)

    def test_feed_subscribe_put_renames(self):
        user, session_token_str = self.generate_credentials()

        feed1 = models.Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = models.Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed2.xml",
            title="Sample Feed 2",
            home_url=FeedTestCase.live_server_url,
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None,
        )

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed1, user=user, custom_feed_title="Custom Title"
        )

        models.SubscribedFeedUserMapping.objects.create(
            feed=feed2, user=user, custom_feed_title="Custom Title 2"
        )

        response = self.client.put(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml&customtitle=Custom%20Title",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)

        response = self.client.put(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml&customtitle=Custom%20Title%202",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn(b"already used", response.content)

    def test_feed_subscribe_delete(self):
        user, session_token_str = self.generate_credentials()

        feed = models.Feed.objects.create(
            feed_url=f"{FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            title="Sample Feed",
            home_url=FeedTestCase.live_server_url,
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None,
        )

        models.SubscribedFeedUserMapping.objects.create(feed=feed, user=user)

        response = self.client.delete(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/well_formed.xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feed_subscribe_delete_not_subscribed(self):
        user, session_token_str = self.generate_credentials()

        response = self.client.delete(
            f"/api/feed/subscribe?url={FeedTestCase.live_server_url}/rss_2.0/sample-404.xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feed_subscribe_delete_no_url(self):
        user, session_token_str = self.generate_credentials()

        response = self.client.delete(
            "/api/feed/subscribe", HTTP_X_SESSION_TOKEN=session_token_str
        )
        self.assertEqual(response.status_code, 400, response.content)
