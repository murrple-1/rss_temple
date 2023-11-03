import datetime
import logging
from io import StringIO
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from api.management.commands.userlabeldaemon import Command
from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedCalculated,
    Feed,
    SubscribedFeedUserMapping,
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

        DaemonTestCase.command._label_loop(3)

        self.assertGreaterEqual(user.calculated_classifier_labels.count(), 1)

    # TODO write tests
