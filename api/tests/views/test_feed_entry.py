import logging
import uuid

import ujson
from django.test import TestCase, tag
from django.utils import timezone

from api.models import Feed, FeedEntry, User


@tag("views")
class FeedEntryTestCase(TestCase):
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

        cls.user = User.objects.create_user("test@test.com", "password")

        cls.feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

    def setUp(self):
        super().setUp()

        self.client.login(email="test@test.com", password="password")

    def test_feedentries_uuid_get(self):
        feed_entry = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        response = self.client.get(
            f"/api/feedentries/{feed_entry.uuid}",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_feedentries_uuid_get_not_found(self):
        response = self.client.get(
            f"/api/feedentries/{uuid.uuid4()}",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feedentries_get(self):
        FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        response = self.client.get(
            "/api/feedentries",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_feedentries_read_post(self):
        feed_entry1 = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 1 Title",
            url="http://example.com/entry1.html",
            content="Some Entry content 1",
            author_name="John Doe",
            db_updated_at=None,
        )

        feed_entry2 = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 2 Title",
            url="http://example.com/entry2.html",
            content="Some Entry content 2",
            author_name="John Doe",
            db_updated_at=None,
        )

        response = self.client.post(
            f"/api/feedentries/read?feedUuid={FeedEntryTestCase.feed.uuid}",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            FeedEntryTestCase.user.read_feed_entries.filter(
                uuid__in=[feed_entry1.uuid, feed_entry2.uuid]
            ).count(),
            2,
        )

        FeedEntryTestCase.user.read_feed_entries.clear()

        response = self.client.post(
            f"/api/feedentries/read?uuid={feed_entry1.uuid},{feed_entry2.uuid}",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            FeedEntryTestCase.user.read_feed_entries.filter(
                uuid__in=[feed_entry1.uuid, feed_entry2.uuid]
            ).count(),
            2,
        )

        FeedEntryTestCase.user.read_feed_entries.clear()

        response = self.client.post(
            f"/api/feedentries/read?uuid={feed_entry1.uuid}",
        )
        self.assertEqual(response.status_code, 204, response.content)

        response = self.client.post(
            f"/api/feedentries/read?feedUuid={FeedEntryTestCase.feed.uuid}",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            FeedEntryTestCase.user.read_feed_entries.filter(
                uuid__in=[feed_entry1.uuid, feed_entry2.uuid]
            ).count(),
            2,
        )

    def test_feedentries_read_post_duplicate(self):
        feed_entry = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        FeedEntryTestCase.user.read_feed_entries.add(feed_entry)

        response = self.client.post(
            f"/api/feedentries/read?uuid={feed_entry.uuid}",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feedentries_read_delete(self):
        feed_entry1 = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 1 Title",
            url="http://example.com/entry1.html",
            content="Some Entry content 1",
            author_name="John Doe",
            db_updated_at=None,
        )

        feed_entry2 = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 2 Title",
            url="http://example.com/entry2.html",
            content="Some Entry content 2",
            author_name="John Doe",
            db_updated_at=None,
        )

        FeedEntryTestCase.user.read_feed_entries.add(feed_entry1, feed_entry2)

        response = self.client.delete(
            f"/api/feedentries/read?uuid={feed_entry1.uuid},{feed_entry2.uuid}",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertFalse(
            FeedEntryTestCase.user.read_feed_entries.filter(
                uuid__in=[feed_entry1.uuid, feed_entry2.uuid]
            ).exists()
        )

    def test_feedentries_favorite_post(self):
        feed_entry1 = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 1 Title",
            url="http://example.com/entry1.html",
            content="Some Entry content 1",
            author_name="John Doe",
            db_updated_at=None,
        )

        feed_entry2 = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 2 Title",
            url="http://example.com/entry2.html",
            content="Some Entry content 2",
            author_name="John Doe",
            db_updated_at=None,
        )

        response = self.client.post(
            f"/api/feedentries/favorite?uuid={feed_entry1.uuid},{feed_entry2.uuid}",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            FeedEntryTestCase.user.favorite_feed_entries.filter(
                uuid__in=[feed_entry1.uuid, feed_entry2.uuid]
            ).count(),
            2,
        )

    def test_feedentries_favorite_post_duplicate(self):
        feed_entry = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        FeedEntryTestCase.user.favorite_feed_entries.add(feed_entry)

        response = self.client.post(
            f"/api/feedentries/favorite?uuid={feed_entry.uuid}",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feedentries_favorite_delete(self):
        feed_entry1 = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 1 Title",
            url="http://example.com/entry1.html",
            content="Some Entry content 1",
            author_name="John Doe",
            db_updated_at=None,
        )

        feed_entry2 = FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 2 Title",
            url="http://example.com/entry2.html",
            content="Some Entry content 2",
            author_name="John Doe",
            db_updated_at=None,
        )

        FeedEntryTestCase.user.favorite_feed_entries.add(feed_entry1, feed_entry2)

        response = self.client.delete(
            "/api/feedentries/favorite",
            ujson.dumps([str(feed_entry1.uuid), str(feed_entry2.uuid)]),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertFalse(
            FeedEntryTestCase.user.favorite_feed_entries.filter(
                uuid__in=[feed_entry1.uuid, feed_entry2.uuid]
            ).exists()
        )

    def test_feedentries_stable_create_post(self):
        response = self.client.post(
            "/api/feedentries/stable",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, str)

    def test_feedentries_stable_post(self):
        FeedEntry.objects.create(
            id=None,
            feed=FeedEntryTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 1 Title",
            url="http://example.com/entry1.html",
            content="Some Entry content 1",
            author_name="John Doe",
            db_updated_at=None,
        )

        response = self.client.post(
            "/api/feedentries/stable",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, str)

        response = self.client.get(
            f"/api/feedentries/stable?token={json_}",
        )

        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, dict)
        self.assertIn("results", json_)
        self.assertIsInstance(json_["results"], list)

    def test_feedentries_stable_post_token_missing(self):
        response = self.client.get(
            "/api/feedentries/stable",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"missing", response.content)

    def test_feedentries_stable_post_token_malformed(self):
        response = self.client.get(
            "/api/feedentries/stable?token=badtoken",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"malformed", response.content)

    def test_feedentries_stable_post_token_valid(self):
        response = self.client.get(
            "/api/feedentries/stable?token=feedentry-0123456789",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, dict)
        self.assertIn("results", json_)
        self.assertIsInstance(json_["results"], list)
