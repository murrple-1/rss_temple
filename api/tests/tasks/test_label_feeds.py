import datetime
import logging
from typing import ClassVar

from django.test import TestCase
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedCalculated,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
    Feed,
    FeedEntry,
    User,
)
from api.tasks.label_feeds import label_feeds


class TaskTestCase(TestCase):
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

    def test_label_feeds(self):
        now = timezone.now()

        user = User.objects.create_user("test@test.com", None)

        label1 = ClassifierLabel.objects.create(text="Label 1")
        label2 = ClassifierLabel.objects.create(text="Label 2")

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=now + datetime.timedelta(days=-1),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entries = FeedEntry.objects.bulk_create(
            FeedEntry(
                feed=feed,
                published_at=now + datetime.timedelta(days=-i),
                title=f"Feed Entry Title {i}",
                url=f"http://example.com/entry{i}.html",
                content=f"Some Entry content for {i}",
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
            )
            for i in range(1, 50, 1)
        )

        ClassifierLabelFeedEntryCalculated.objects.bulk_create(
            ClassifierLabelFeedEntryCalculated(
                feed_entry=feed_entry,
                classifier_label=label1,
                expires_at=(now + datetime.timedelta(days=7)),
            )
            for feed_entry in feed_entries[0:15]
        )
        ClassifierLabelFeedEntryCalculated.objects.bulk_create(
            ClassifierLabelFeedEntryCalculated(
                feed_entry=feed_entry,
                classifier_label=label2,
                expires_at=(now + datetime.timedelta(days=7)),
            )
            for feed_entry in feed_entries[10:30]
        )
        ClassifierLabelFeedEntryVote.objects.bulk_create(
            ClassifierLabelFeedEntryVote(
                feed_entry=feed_entry, classifier_label=label1, user=user
            )
            for feed_entry in feed_entries[15:25]
        )
        ClassifierLabelFeedEntryVote.objects.bulk_create(
            ClassifierLabelFeedEntryVote(
                feed_entry=feed_entry, classifier_label=label2, user=user
            )
            for feed_entry in feed_entries[20:40]
        )

        label_feeds(3, datetime.timedelta(days=7))

        self.assertGreaterEqual(feed.calculated_classifier_labels.count(), 1)

    def test_label_feeds_populates_weight(self):
        now = timezone.now()
        user = User.objects.create_user("weight-feeds@test.com", None)
        label1 = ClassifierLabel.objects.create(text="Label 1")
        label2 = ClassifierLabel.objects.create(text="Label 2")

        feed = Feed.objects.create(
            feed_url="http://example.com/weight.xml",
            title="Weight Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_entries = FeedEntry.objects.bulk_create(
            FeedEntry(
                feed=feed,
                published_at=now + datetime.timedelta(days=-i),
                title=f"Entry {i}",
                url=f"http://example.com/w{i}.html",
                content=f"content {i}",
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
            )
            for i in range(4)
        )

        # label1: 2 human votes -> 2.0
        ClassifierLabelFeedEntryVote.objects.bulk_create(
            ClassifierLabelFeedEntryVote(
                feed_entry=fe, classifier_label=label1, user=user
            )
            for fe in feed_entries[0:2]
        )
        # label2: 2 calculated at 0.25 -> 0.5
        ClassifierLabelFeedEntryCalculated.objects.bulk_create(
            ClassifierLabelFeedEntryCalculated(
                feed_entry=fe,
                classifier_label=label2,
                expires_at=now + datetime.timedelta(days=7),
                weight=0.25,
            )
            for fe in feed_entries[2:4]
        )

        label_feeds(3, datetime.timedelta(days=7))

        rows = {
            r.classifier_label_id: r.weight
            for r in ClassifierLabelFeedCalculated.objects.filter(feed=feed)
        }
        self.assertAlmostEqual(rows[label1.uuid], 2.0)
        self.assertAlmostEqual(rows[label2.uuid], 0.5)

    def test_label_feeds_skips_feeds_without_signal(self):
        now = timezone.now()
        Feed.objects.create(
            feed_url="http://example.com/silent.xml",
            title="Silent Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )

        label_feeds(3, datetime.timedelta(days=7))

        self.assertEqual(ClassifierLabelFeedCalculated.objects.count(), 0)

    def test_label_feeds_respects_top_x(self):
        now = timezone.now()
        user = User.objects.create_user("topx@test.com", None)
        labels = [
            ClassifierLabel.objects.create(text=f"Top Label {i}") for i in range(5)
        ]
        feed = Feed.objects.create(
            feed_url="http://example.com/topx.xml",
            title="TopX Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_entry = FeedEntry.objects.create(
            feed=feed,
            published_at=now,
            title="Entry",
            url="http://example.com/topx-entry.html",
            content="content",
            author_name="John Doe",
            db_updated_at=None,
            is_archived=False,
        )
        for label in labels:
            ClassifierLabelFeedEntryVote.objects.create(
                feed_entry=feed_entry, classifier_label=label, user=user
            )

        label_feeds(2, datetime.timedelta(days=7))

        self.assertEqual(
            ClassifierLabelFeedCalculated.objects.filter(feed=feed).count(), 2
        )

    def test_label_feeds_chunk_boundaries(self):
        now = timezone.now()
        user = User.objects.create_user("chunks@test.com", None)
        label = ClassifierLabel.objects.create(text="Chunk Label")

        for i in range(3):
            feed = Feed.objects.create(
                feed_url=f"http://example.com/chunk{i}.xml",
                title=f"Chunk Feed {i}",
                home_url="http://example.com",
                published_at=now,
                updated_at=None,
                db_updated_at=None,
            )
            feed_entry = FeedEntry.objects.create(
                feed=feed,
                published_at=now,
                title=f"Entry {i}",
                url=f"http://example.com/chunk-entry{i}.html",
                content="content",
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
            )
            ClassifierLabelFeedEntryVote.objects.create(
                feed_entry=feed_entry, classifier_label=label, user=user
            )

        label_feeds(3, datetime.timedelta(days=7), chunk_size=2)

        self.assertEqual(ClassifierLabelFeedCalculated.objects.count(), 3)

    def test_label_feeds_rerun_skips_already_labelled_unexpired_feeds(self):
        # `label_feeds` runs nightly against a 7-day expiry interval, so on 6 of
        # every 7 nights it re-runs while a feed's row from a previous run is
        # still unexpired. `bulk_create` is called without `ignore_conflicts`,
        # and `ClassifierLabelFeedCalculated` has a unique constraint on
        # (classifier_label, feed) -- so if the `already_labelled` exclusion is
        # ever dropped, a second run over the same unexpired feed raises
        # `IntegrityError` instead of leaving the existing row untouched.
        now = timezone.now()
        user = User.objects.create_user("rerun-feeds@test.com", None)
        label = ClassifierLabel.objects.create(text="Rerun Label")
        feed = Feed.objects.create(
            feed_url="http://example.com/rerun.xml",
            title="Rerun Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_entry = FeedEntry.objects.create(
            feed=feed,
            published_at=now,
            title="Rerun Entry",
            url="http://example.com/rerun-entry.html",
            content="content",
            author_name="John Doe",
            db_updated_at=None,
            is_archived=False,
        )
        ClassifierLabelFeedEntryVote.objects.create(
            feed_entry=feed_entry, classifier_label=label, user=user
        )

        label_feeds(3, datetime.timedelta(days=7))

        self.assertEqual(
            ClassifierLabelFeedCalculated.objects.filter(feed=feed).count(), 1
        )
        row = ClassifierLabelFeedCalculated.objects.get(feed=feed)
        original_expires_at = row.expires_at

        # Second run: the row above is still unexpired. This must not attempt
        # to re-create it.
        label_feeds(3, datetime.timedelta(days=7))

        self.assertEqual(
            ClassifierLabelFeedCalculated.objects.filter(feed=feed).count(), 1
        )
        row.refresh_from_db()
        self.assertEqual(row.expires_at, original_expires_at)
