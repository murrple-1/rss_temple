import datetime
import logging
from typing import ClassVar

from django.test import TestCase
from django.utils import timezone

from api.models import (
    ClassifierLabel,
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

    # TODO write tests
