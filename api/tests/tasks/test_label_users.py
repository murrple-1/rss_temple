import datetime
import logging
from typing import ClassVar

from django.test import TestCase
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedCalculated,
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
