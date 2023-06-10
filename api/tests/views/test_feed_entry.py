import logging
import uuid
from typing import ClassVar

import ujson
from django.db import transaction
from django.utils import timezone

from api.models import (
    FavoriteFeedEntryUserMapping,
    Feed,
    FeedEntry,
    ReadFeedEntryUserMapping,
    User,
)
from api.tests.views import ViewTestCase


class FeedEntryTestCase(ViewTestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]
    user: ClassVar[User]
    feed: ClassVar[Feed]

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

        self.client.force_login(FeedEntryTestCase.user)

    def test_feedentry_get(self):
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
            f"/api/feedentry/{feed_entry.uuid}",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_feedentry_get_not_found(self):
        response = self.client.get(
            f"/api/feedentry/{uuid.uuid4()}",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feedentries_query_post(self):
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

        response = self.client.post(
            "/api/feedentries/query",
            ujson.dumps({}),
            "application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_feedentry_read_post(self):
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

        response = self.client.post(
            f"/api/feedentry/{feed_entry.uuid}/read",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, str)

        self.assertTrue(
            ReadFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry=feed_entry
            ).exists()
        )

    def test_feedentry_read_post_not_found(self):
        response = self.client.post(
            f"/api/feedentry/{uuid.uuid4()}/read",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feedentry_read_post_duplicate(self):
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

        ReadFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry
        )

        with transaction.atomic():
            response = self.client.post(
                f"/api/feedentry/{feed_entry.uuid}/read",
            )
            self.assertEqual(response.status_code, 200, response.content)

        self.assertTrue(
            ReadFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry=feed_entry
            ).exists()
        )

    def test_feedentry_read_delete(self):
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

        ReadFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry
        )

        response = self.client.delete(
            f"/api/feedentry/{feed_entry.uuid}/read",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertFalse(
            ReadFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry=feed_entry
            ).exists()
        )

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
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedUuids": [str(FeedEntryTestCase.feed.uuid)],
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            ReadFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]
            ).count(),
            2,
        )

        ReadFeedEntryUserMapping.objects.all().delete()

        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedEntryUuids": [str(feed_entry1.uuid), str(feed_entry2.uuid)],
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            ReadFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]
            ).count(),
            2,
        )

        ReadFeedEntryUserMapping.objects.all().delete()

        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedEntryUuids": [str(feed_entry1.uuid)],
                    "feedUuids": [str(FeedEntryTestCase.feed.uuid)],
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            ReadFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]
            ).count(),
            2,
        )

    def test_feedentries_read_post_noentries(self):
        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps({}),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentries_read_post_typeerror(self):
        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps([]),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentries_read_post_feeduuids_typeerror(self):
        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedUuids": 0,
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentries_read_post_feeduuids_element_typeerror(self):
        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedUuids": [0],
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentries_read_post_feeduuids_element_malformed(self):
        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedUuids": ["baduuid"],
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentries_read_post_feedentryuuids_typeerror(self):
        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedEntryUuids": 0,
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentries_read_post_feedentryuuids_element_typeerror(self):
        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedEntryUuids": [0],
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentries_read_post_feedentryuuids_element_malformed(self):
        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedEntryUuids": ["baduuid"],
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

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

        ReadFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry, user=FeedEntryTestCase.user
        )

        response = self.client.post(
            "/api/feedentries/read",
            ujson.dumps(
                {
                    "feedEntryUuids": [str(feed_entry.uuid)],
                }
            ),
            "application/json",
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

        ReadFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry1
        )

        ReadFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry2
        )

        response = self.client.delete(
            "/api/feedentries/read",
            ujson.dumps([str(feed_entry1.uuid), str(feed_entry2.uuid)]),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertFalse(
            ReadFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]
            ).exists()
        )

    def test_feedentries_read_delete_shortcut(self):
        response = self.client.delete(
            "/api/feedentries/read",
            ujson.dumps([]),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feedentries_read_delete_malformed(self):
        response = self.client.delete(
            "/api/feedentries/read",
            ujson.dumps([0]),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentry_favorite_post(self):
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

        response = self.client.post(
            f"/api/feedentry/{feed_entry.uuid}/favorite",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertTrue(
            FavoriteFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry=feed_entry
            ).exists()
        )

    def test_feedentry_favorite_post_not_found(self):
        response = self.client.post(
            f"/api/feedentry/{uuid.uuid4()}/favorite",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_feedentry_favorite_post_duplicate(self):
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

        FavoriteFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry, user=FeedEntryTestCase.user
        )

        response = self.client.post(
            f"/api/feedentry/{feed_entry.uuid}/favorite",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feedentry_favorite_delete(self):
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

        FavoriteFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry
        )

        response = self.client.delete(
            f"/api/feedentry/{feed_entry.uuid}/favorite",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertFalse(
            FavoriteFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry=feed_entry
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
            "/api/feedentries/favorite",
            ujson.dumps([str(feed_entry1.uuid), str(feed_entry2.uuid)]),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            FavoriteFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]
            ).count(),
            2,
        )

    def test_feedentries_favorite_post_shortcut(self):
        response = self.client.post(
            "/api/feedentries/favorite",
            ujson.dumps([]),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feedentries_favorite_post_malformed(self):
        response = self.client.post(
            "/api/feedentries/favorite",
            ujson.dumps([0]),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentries_favorite_post_not_found(self):
        response = self.client.post(
            "/api/feedentries/favorite",
            ujson.dumps([str(uuid.uuid4())]),
            "application/json",
        )
        self.assertEqual(response.status_code, 404, response.content)

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

        FavoriteFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry, user=FeedEntryTestCase.user
        )

        response = self.client.post(
            "/api/feedentries/favorite",
            ujson.dumps([str(feed_entry.uuid)]),
            "application/json",
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

        FavoriteFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry1
        )

        FavoriteFeedEntryUserMapping.objects.create(
            user=FeedEntryTestCase.user, feed_entry=feed_entry2
        )

        response = self.client.delete(
            "/api/feedentries/favorite",
            ujson.dumps([str(feed_entry1.uuid), str(feed_entry2.uuid)]),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertFalse(
            FavoriteFeedEntryUserMapping.objects.filter(
                user=FeedEntryTestCase.user, feed_entry__in=[feed_entry1, feed_entry2]
            ).exists()
        )

    def test_feedentries_favorite_delete_shortcut(self):
        response = self.client.delete(
            "/api/feedentries/favorite",
            ujson.dumps([]),
            "application/json",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_feedentries_favorite_delete_malformed(self):
        response = self.client.delete(
            "/api/feedentries/favorite",
            ujson.dumps([0]),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_feedentries_query_stable_create_post(self):
        response = self.client.post(
            "/api/feedentries/query/stable/create",
            ujson.dumps({}),
            "application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, str)

    def test_feedentries_query_stable_post(self):
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
            "/api/feedentries/query/stable/create",
            ujson.dumps({}),
            "application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, str)

        response = self.client.post(
            "/api/feedentries/query/stable",
            ujson.dumps(
                {
                    "token": json_,
                }
            ),
            "application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, dict)
        self.assertIn("objects", json_)
        self.assertIsInstance(json_["objects"], list)

    def test_feedentries_query_stable_post_token_missing(self):
        response = self.client.post(
            "/api/feedentries/query/stable",
            ujson.dumps({}),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"missing", response.content)

    def test_feedentries_query_stable_post_token_typeerror(self):
        response = self.client.post(
            "/api/feedentries/query/stable",
            ujson.dumps(
                {
                    "token": 0,
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"must be", response.content)

    def test_feedentries_query_stable_post_token_malformed(self):
        response = self.client.post(
            "/api/feedentries/query/stable",
            ujson.dumps(
                {
                    "token": "badtoken",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(b"token", response.content)
        self.assertIn(b"malformed", response.content)

    def test_feedentries_query_stable_post_token_valid(self):
        response = self.client.post(
            "/api/feedentries/query/stable",
            ujson.dumps(
                {
                    "token": "feedentry-0123456789",
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = ujson.loads(response.content)
        self.assertIsInstance(json_, dict)
        self.assertIn("objects", json_)
        self.assertIsInstance(json_["objects"], list)
