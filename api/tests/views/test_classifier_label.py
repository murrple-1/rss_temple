import datetime
import logging
import uuid
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
            f"/api/classifierlabels",
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

        cache.clear()
        response = self.client.get(
            f"/api/classifierlabels", {"feedEntryUuid": str(feed_entry.uuid)}
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertGreaterEqual(len(json_), 1)

        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label1,
            feed_entry=feed_entry,
            user=ClassifierLabelTestCase.user,
        )

        cache.clear()
        response = self.client.get(
            f"/api/classifierlabels", {"feedEntryUuid": str(feed_entry.uuid)}
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertGreaterEqual(len(json_), 1)
        self.assertIn("text", json_[0])
        self.assertEqual(json_[0]["text"], "Label 1")

        user2 = User.objects.create_user("test2@test.com", None)

        ClassifierLabelFeedEntryCalculated.objects.create(
            classifier_label=label2,
            feed_entry=feed_entry,
            expires_at=(timezone.now() + datetime.timedelta(days=7)),
        )
        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label2, feed_entry=feed_entry, user=user2
        )

        cache.clear()
        response = self.client.get(
            f"/api/classifierlabels", {"feedEntryUuid": str(feed_entry.uuid)}
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertGreaterEqual(len(json_), 1)
        self.assertIn("text", json_[0])
        self.assertEqual(json_[0]["text"], "Label 2")

    def test_ClassifierLabelListView_get_feed_entry_notfound(self):
        response = self.client.get(
            f"/api/classifierlabels", {"feedEntryUuid": str(uuid.UUID(int=0))}
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_ClassifierLabelListByEntryView_post_feed_entry(self):
        cache: BaseCache = caches["default"]

        label1 = ClassifierLabel.objects.create(text="Label 1")
        label2 = ClassifierLabel.objects.create(text="Label 2")

        feed_entry1 = FeedEntry.objects.create(
            id=None,
            feed=ClassifierLabelTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title 1",
            url="http://example.com/entry1.html",
            content="Some Entry content 1",
            author_name="John Doe",
            db_updated_at=None,
        )

        feed_entry2 = FeedEntry.objects.create(
            id=None,
            feed=ClassifierLabelTestCase.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title 2",
            url="http://example.com/entry2.html",
            content="Some Entry content 2",
            author_name="John Doe",
            db_updated_at=None,
        )

        cache.clear()

        # do it once to "warm" the `get_classifier_label_vote_counts_from_cache()` cache
        response = self.client.post(
            f"/api/classifierlabels/entries",
            {"feedEntryUuids": [str(feed_entry1.uuid)]},
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), dict)
        self.assertIn("classifierLabels", json_)
        self.assertIs(type(json_["classifierLabels"]), dict)
        self.assertIn(str(feed_entry1.uuid), json_["classifierLabels"])
        self.assertGreaterEqual(
            len(json_["classifierLabels"][str(feed_entry1.uuid)]), 1
        )

        # do it a second time with the "warmed" `get_classifier_label_vote_counts_from_cache()` cache,
        # so the code path is slightly different
        response = self.client.post(
            f"/api/classifierlabels/entries",
            {"feedEntryUuids": [str(feed_entry1.uuid), str(feed_entry2.uuid)]},
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), dict)
        self.assertIn("classifierLabels", json_)
        self.assertIs(type(json_["classifierLabels"]), dict)
        self.assertIn(str(feed_entry1.uuid), json_["classifierLabels"])
        self.assertGreaterEqual(
            len(json_["classifierLabels"][str(feed_entry1.uuid)]), 1
        )

        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label1,
            feed_entry=feed_entry1,
            user=ClassifierLabelTestCase.user,
        )

        cache.clear()
        response = self.client.post(
            f"/api/classifierlabels/entries",
            {"feedEntryUuids": [str(feed_entry1.uuid), str(feed_entry2.uuid)]},
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), dict)
        self.assertIn("classifierLabels", json_)
        self.assertIs(type(json_["classifierLabels"]), dict)
        self.assertIn(str(feed_entry1.uuid), json_["classifierLabels"])
        self.assertGreaterEqual(
            len(json_["classifierLabels"][str(feed_entry1.uuid)]), 1
        )
        self.assertIn("text", json_["classifierLabels"][str(feed_entry1.uuid)][0])
        self.assertEqual(
            json_["classifierLabels"][str(feed_entry1.uuid)][0]["text"], "Label 1"
        )

        user2 = User.objects.create_user("test2@test.com", None)

        ClassifierLabelFeedEntryCalculated.objects.create(
            classifier_label=label2,
            feed_entry=feed_entry1,
            expires_at=(timezone.now() + datetime.timedelta(days=7)),
        )
        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label2, feed_entry=feed_entry1, user=user2
        )

        cache.clear()
        response = self.client.post(
            f"/api/classifierlabels/entries",
            {"feedEntryUuids": [str(feed_entry1.uuid), str(feed_entry2.uuid)]},
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), dict)
        self.assertIn("classifierLabels", json_)
        self.assertIs(type(json_["classifierLabels"]), dict)
        self.assertIn(str(feed_entry1.uuid), json_["classifierLabels"])
        self.assertGreaterEqual(
            len(json_["classifierLabels"][str(feed_entry1.uuid)]), 1
        )
        self.assertIn("text", json_["classifierLabels"][str(feed_entry1.uuid)][0])
        self.assertEqual(
            json_["classifierLabels"][str(feed_entry1.uuid)][0]["text"], "Label 2"
        )

    def test_ClassifierLabelListByEntryView_post_feed_entry_notfound(self):
        response = self.client.post(
            f"/api/classifierlabels/entries",
            {"feedEntryUuids": [str(uuid.UUID(int=0))]},
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_ClassifierLabelListByEntryView_post_emptyqueryset(self):
        # this tests the `get_counts_lookup_from_cache()` code when the queryset is empty
        cache: BaseCache = caches["default"]

        label1 = ClassifierLabel.objects.create(text="Label 1")
        label2 = ClassifierLabel.objects.create(text="Label 2")

        cache.clear()
        response = self.client.post(
            f"/api/classifierlabels/entries",
            {"feedEntryUuids": []},
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), dict)
        self.assertIn("classifierLabels", json_)
        self.assertIs(type(json_["classifierLabels"]), dict)

    def test_ClassifierLabelFeedEntryVotesView_get(self):
        label1 = ClassifierLabel.objects.create(text="Label 1")
        ClassifierLabel.objects.create(text="Label 2")

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

        user2 = User.objects.create_user("test2@test.com", None)

        response = self.client.get(
            f"/api/classifierlabels/votes/{feed_entry.uuid}",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertEqual(len(json_), 0)

        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label1,
            feed_entry=feed_entry,
            user=user2,
        )

        response = self.client.get(
            f"/api/classifierlabels/votes/{feed_entry.uuid}",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertEqual(len(json_), 0)

        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label1,
            feed_entry=feed_entry,
            user=ClassifierLabelTestCase.user,
        )

        response = self.client.get(
            f"/api/classifierlabels/votes/{feed_entry.uuid}",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), list)
        self.assertEqual(len(json_), 1)

    def test_ClassifierLabelFeedEntryVotesView_get_notfound(self):
        response = self.client.get(
            f"/api/classifierlabels/votes/{uuid.UUID(int=0)}",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_ClassifierLabelFeedEntryVotesView_post(self):
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

        response = self.client.post(
            f"/api/classifierlabels/votes/{feed_entry.uuid}",
            {
                "classifierLabelUuids": [str(label1.uuid), str(label2.uuid)],
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            ClassifierLabelFeedEntryVote.objects.filter(feed_entry=feed_entry).count(),
            2,
        )

        response = self.client.post(
            f"/api/classifierlabels/votes/{feed_entry.uuid}",
            {
                "classifierLabelUuids": [],
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            ClassifierLabelFeedEntryVote.objects.filter(feed_entry=feed_entry).count(),
            0,
        )

    def test_ClassifierLabelFeedEntryVotesView_post_notfound(self):
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

        response = self.client.post(
            f"/api/classifierlabels/votes/{uuid.UUID(int=0)}",
            {
                "classifierLabelUuids": [],
            },
        )
        self.assertEqual(response.status_code, 404, response.content)

        response = self.client.post(
            f"/api/classifierlabels/votes/{feed_entry.uuid}",
            {
                "classifierLabelUuids": [str(uuid.UUID(int=0))],
            },
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_ClassifierLabelVotesListView_get(self):
        label1 = ClassifierLabel.objects.create(text="Label 1")
        ClassifierLabel.objects.create(text="Label 2")

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

        response = self.client.get(
            f"/api/classifierlabels/votes",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), dict)
        self.assertIn("objects", json_)
        self.assertIs(type(json_["objects"]), list)
        self.assertEqual(len(json_["objects"]), 0)

        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label1,
            feed_entry=feed_entry,
            user=ClassifierLabelTestCase.user,
        )

        response = self.client.get(
            f"/api/classifierlabels/votes",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()
        self.assertIs(type(json_), dict)
        self.assertIn("objects", json_)
        self.assertIs(type(json_["objects"]), list)
        self.assertEqual(len(json_["objects"]), 1)
        self.assertEqual(
            json_["objects"][0],
            {
                "feedEntryUuid": str(feed_entry.uuid),
                "classifierLabelUuids": [str(label1.uuid)],
            },
        )
