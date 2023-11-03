import datetime
import logging
from io import StringIO
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from api.management.commands.feedlabeldaemon import Command
from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
    Feed,
    FeedEntry,
    User,
)

if TYPE_CHECKING:
    from unittest.mock import _Mock, _patch


class DaemonTestCase(TestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]

    command: ClassVar[Command]
    stdout_patcher: ClassVar["_patch[_Mock]"]
    stderr_patcher: ClassVar["_patch[_Mock]"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)
        logging.getLogger("django").setLevel(logging.CRITICAL)

        cls.command = Command()
        cls.stdout_patcher = patch.object(cls.command, "stdout", new_callable=StringIO)
        cls.stderr_patcher = patch.object(cls.command, "stderr", new_callable=StringIO)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    def setUp(self):
        super().setUp()

        self.stdout_patcher.start()
        self.stderr_patcher.start()

    def tearDown(self):
        super().tearDown()

        self.stdout_patcher.stop()
        self.stderr_patcher.stop()

    def test_label_loop(self):
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

        DaemonTestCase.command._label_loop(3)

        self.assertGreaterEqual(feed.calculated_classifier_labels.count(), 1)

    # TODO write tests
