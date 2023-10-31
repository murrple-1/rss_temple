import logging
from typing import ClassVar

from django.core.cache import BaseCache, caches
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
    Feed,
    FeedEntry,
    User,
)
from api.tests.utils import throttling_monkey_patch


class ClassifierLabelTestCase(APITestCase):
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

        throttling_monkey_patch()

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

        self.client.force_authenticate(user=ClassifierLabelTestCase.user)

    def test_ClassifierLabelListView_get(self):
        ClassifierLabel.objects.create(text="Label 1")

        response = self.client.get(
            f"/api/classififerlabels",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertGreaterEqual(len(json_), 1)

    def test_ClassifierLabelListView_get_feed_entry(self):
        cache: BaseCache = caches["default"]

        label1 = ClassifierLabel.objects.create(text="Label 1")
        label2 = ClassifierLabel.objects.create(text="Label 2")

        feed_entry = FeedEntry.objects.create(
            id=None,
            feed=ClassifierLabelTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        cache_key = f"classifier_label_votes__{feed_entry.uuid}"

        response = self.client.get(
            f"/api/classififerlabels", {"feedEntryUuid": str(feed_entry.uuid)}
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertGreaterEqual(len(json_), 1)

        self.assertTrue(cache.delete(cache_key))

        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label1,
            feed_entry=feed_entry,
            user=ClassifierLabelTestCase.user,
        )

        response = self.client.get(
            f"/api/classififerlabels", {"feedEntryUuid": str(feed_entry.uuid)}
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertGreaterEqual(len(json_), 1)
        self.assertIn("text", json_[0])
        self.assertEqual(json_[0]["text"], "Label 1")

        self.assertTrue(cache.delete(cache_key))

        user2 = User.objects.create_user("test2@test.com", None)

        ClassifierLabelFeedEntryCalculated.objects.create(
            classifier_label=label2, feed_entry=feed_entry
        )
        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label2, feed_entry=feed_entry, user=user2
        )

        response = self.client.get(
            f"/api/classififerlabels", {"feedEntryUuid": str(feed_entry.uuid)}
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertGreaterEqual(len(json_), 1)
        self.assertIn("text", json_[0])
        self.assertEqual(json_[0]["text"], "Label 2")

        self.assertTrue(cache.delete(cache_key))
