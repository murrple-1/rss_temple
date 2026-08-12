import datetime
import logging
from typing import ClassVar

from django.test import TestCase
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedCalculated,
    ClassifierLabelUserCalculated,
    Feed,
    SubscribedFeedUserMapping,
    User,
)
from api.tasks.label_users import label_users


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

    def test_label_users(self):
        now = timezone.now()

        user = User.objects.create_user("test@test.com", None)

        label1 = ClassifierLabel.objects.create(text="Label 1")
        label2 = ClassifierLabel.objects.create(text="Label 2")

        feeds = Feed.objects.bulk_create(
            Feed(
                feed_url=f"http://example{i}.com/rss.xml",
                title=f"Sample Feed {i}",
                home_url=f"http://example{i}.com",
                published_at=now + datetime.timedelta(days=-1),
                updated_at=None,
                db_updated_at=None,
            )
            for i in range(50)
        )

        SubscribedFeedUserMapping.objects.bulk_create(
            SubscribedFeedUserMapping(
                feed=feed,
                user=user,
            )
            for feed in feeds[0:15]
        )
        ClassifierLabelFeedCalculated.objects.bulk_create(
            ClassifierLabelFeedCalculated(
                feed=feed,
                classifier_label=label1,
                expires_at=(now + datetime.timedelta(days=7)),
            )
            for feed in feeds[10:35]
        )
        ClassifierLabelFeedCalculated.objects.bulk_create(
            ClassifierLabelFeedCalculated(
                feed=feed,
                classifier_label=label2,
                expires_at=(now + datetime.timedelta(days=7)),
            )
            for feed in feeds[15:40]
        )

        label_users(3, datetime.timedelta(days=7))

        self.assertGreaterEqual(user.calculated_classifier_labels.count(), 1)

    def test_label_users_sums_feed_weights(self):
        now = timezone.now()
        user = User.objects.create_user("weight-users@test.com", None)
        label1 = ClassifierLabel.objects.create(text="User Label 1")
        label2 = ClassifierLabel.objects.create(text="User Label 2")

        feed_a = Feed.objects.create(
            feed_url="http://example.com/a.xml",
            title="Feed A",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_b = Feed.objects.create(
            feed_url="http://example.com/b.xml",
            title="Feed B",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        SubscribedFeedUserMapping.objects.create(feed=feed_a, user=user)
        SubscribedFeedUserMapping.objects.create(feed=feed_b, user=user)

        expires = now + datetime.timedelta(days=7)
        ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label1, feed=feed_a, expires_at=expires, weight=2.0
        )
        ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label1, feed=feed_b, expires_at=expires, weight=0.5
        )
        ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label2, feed=feed_b, expires_at=expires, weight=1.25
        )

        label_users(10, datetime.timedelta(days=7))

        rows = {
            r.classifier_label_id: r.weight
            for r in ClassifierLabelUserCalculated.objects.filter(user=user)
        }
        self.assertAlmostEqual(rows[label1.uuid], 2.5)
        self.assertAlmostEqual(rows[label2.uuid], 1.25)

    def test_label_users_skips_users_without_subscriptions(self):
        User.objects.create_user("nosubs@test.com", None)

        label_users(10, datetime.timedelta(days=7))

        self.assertEqual(ClassifierLabelUserCalculated.objects.count(), 0)

    def test_label_users_chunk_boundaries(self):
        now = timezone.now()
        label = ClassifierLabel.objects.create(text="Chunk User Label")
        feed = Feed.objects.create(
            feed_url="http://example.com/shared.xml",
            title="Shared Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label,
            feed=feed,
            expires_at=now + datetime.timedelta(days=7),
            weight=1.0,
        )
        for i in range(3):
            user = User.objects.create_user(f"chunkuser{i}@test.com", None)
            SubscribedFeedUserMapping.objects.create(feed=feed, user=user)

        label_users(10, datetime.timedelta(days=7), chunk_size=2)

        self.assertEqual(ClassifierLabelUserCalculated.objects.count(), 3)

    def test_label_users_rerun_skips_already_labelled_unexpired_users(self):
        # Mirrors test_label_feeds_rerun_skips_already_labelled_unexpired_feeds:
        # `label_users` runs nightly against a 7-day expiry interval, so it
        # re-runs on 6 of every 7 nights while a user's row from a previous run
        # is still unexpired. `bulk_create` is called without
        # `ignore_conflicts`, and `ClassifierLabelUserCalculated` has a unique
        # constraint on (classifier_label, user) -- so if the
        # `already_labelled` exclusion is ever dropped, a second run over the
        # same unexpired user raises `IntegrityError` instead of leaving the
        # existing row untouched.
        now = timezone.now()
        user = User.objects.create_user("rerun-users@test.com", None)
        label = ClassifierLabel.objects.create(text="Rerun User Label")
        feed = Feed.objects.create(
            feed_url="http://example.com/rerun-users.xml",
            title="Rerun Users Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        SubscribedFeedUserMapping.objects.create(feed=feed, user=user)
        ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label,
            feed=feed,
            expires_at=now + datetime.timedelta(days=7),
            weight=1.0,
        )

        label_users(10, datetime.timedelta(days=7))

        self.assertEqual(
            ClassifierLabelUserCalculated.objects.filter(user=user).count(), 1
        )
        row = ClassifierLabelUserCalculated.objects.get(user=user)
        original_expires_at = row.expires_at

        # Second run: the row above is still unexpired. This must not attempt
        # to re-create it.
        label_users(10, datetime.timedelta(days=7))

        self.assertEqual(
            ClassifierLabelUserCalculated.objects.filter(user=user).count(), 1
        )
        row.refresh_from_db()
        self.assertEqual(row.expires_at, original_expires_at)
