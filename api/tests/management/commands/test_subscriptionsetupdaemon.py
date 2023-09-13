import logging
from io import StringIO
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

from django.test import tag
from django.utils import timezone

from api.management.commands.subscriptionsetupdaemon import Command
from api.models import (
    Feed,
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
    SubscribedFeedUserMapping,
    User,
    UserCategory,
)
from api.tests import TestFileServerTestCase
from api.tests.utils import db_migrations_state

if TYPE_CHECKING:
    from unittest.mock import _Mock, _patch


class DaemonTestCase(TestFileServerTestCase):
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

        db_migrations_state()

    def tearDown(self):
        super().tearDown()

        self.stdout_patcher.stop()
        self.stderr_patcher.stop()

    def generate_credentials(self):
        return User.objects.create_user("test@test.com", None)

    def test_get_first_entry(self):
        user = self.generate_credentials()

        feed_subscription_progress_entry = self.command._get_first_entry()

        self.assertIsNone(feed_subscription_progress_entry)

        feed_subscription_progress_entry = FeedSubscriptionProgressEntry.objects.create(
            user=user
        )

        self.assertEqual(
            feed_subscription_progress_entry.status,
            FeedSubscriptionProgressEntry.NOT_STARTED,
        )

        feed_subscription_progress_entry = self.command._get_first_entry()

        self.assertIsNotNone(feed_subscription_progress_entry)
        assert feed_subscription_progress_entry is not None
        self.assertEqual(
            feed_subscription_progress_entry.status,
            FeedSubscriptionProgressEntry.STARTED,
        )

    @tag("slow")
    def test_do_subscription(self):
        user = self.generate_credentials()

        feed1 = Feed.objects.create(
            feed_url=f"{DaemonTestCase.live_server_url}/rss_2.0/well_formed.xml?_=existing",
            title="Sample Feed",
            home_url=DaemonTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url=f"{DaemonTestCase.live_server_url}/rss_2.0/well_formed.xml?_=existing_with_custom_title",
            title="Sample Feed",
            home_url=DaemonTestCase.live_server_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(feed=feed1, user=user)
        SubscribedFeedUserMapping.objects.create(
            feed=feed2, user=user, custom_feed_title="Old Custom Title"
        )

        UserCategory.objects.create(user=user, text="Old User Category")

        feed_subscription_progress_entry = FeedSubscriptionProgressEntry.objects.create(
            user=user
        )

        self.assertEqual(
            feed_subscription_progress_entry.status,
            FeedSubscriptionProgressEntry.NOT_STARTED,
        )

        count = 0
        for feed_url in [
            f"{DaemonTestCase.live_server_url}/rss_2.0/well_formed.xml",
            f"{DaemonTestCase.live_server_url}/rss_2.0/well_formed.xml?_={{s}}",
            f"{DaemonTestCase.live_server_url}/rss_2.0/sample-404.xml",
            f"{DaemonTestCase.live_server_url}/rss_2.0/sample-404.xml?_={{s}}",
        ]:
            for custom_feed_title in [
                None,
                "Old Custom Title",
                "New Custom Title",
                "New Custom Title {s}",
                "Sample Feed",
            ]:
                for user_category_text in [
                    None,
                    "Old User Category",
                    "New User Category",
                    "New User Category {s}",
                ]:
                    feed_subscription_progress_entry_descriptor = FeedSubscriptionProgressEntryDescriptor.objects.create(
                        feed_subscription_progress_entry=feed_subscription_progress_entry,
                        feed_url=feed_url.format(s=count),
                        custom_feed_title=None
                        if custom_feed_title is None
                        else custom_feed_title.format(s=count),
                        user_category_text=None
                        if user_category_text is None
                        else user_category_text.format(s=count),
                    )
                    self.assertFalse(
                        feed_subscription_progress_entry_descriptor.is_finished
                    )

                    count += 1

        feed_subscription_progress_entry = self.command._get_first_entry()

        assert feed_subscription_progress_entry is not None
        self.assertEqual(
            feed_subscription_progress_entry.status,
            FeedSubscriptionProgressEntry.STARTED,
        )

        self.command._do_subscription(feed_subscription_progress_entry)

        self.assertEqual(
            feed_subscription_progress_entry.status,
            FeedSubscriptionProgressEntry.FINISHED,
        )
