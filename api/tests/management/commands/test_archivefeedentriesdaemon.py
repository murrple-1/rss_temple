import datetime
import logging
from io import StringIO
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

from django.utils import timezone

from api.management.commands.archivefeedentriesdaemon import Command
from api.models import Feed, FeedEntry
from api.tests import TestFileServerTestCase

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

    def tearDown(self):
        super().tearDown()

        self.stdout_patcher.stop()
        self.stderr_patcher.stop()

    def test_handle_feed(self):
        now = timezone.now()

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=now + datetime.timedelta(days=-1),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entries = [
            FeedEntry.objects.create(
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
        ]

        DaemonTestCase.command._handle_feed(
            feed, now, datetime.timedelta(days=-30), 5, 60 * 60 * 24
        )

        for feed_entry in feed_entries:
            feed_entry.refresh_from_db()

        feed.refresh_from_db()

        self.assertTrue(any(fe.is_archived for fe in feed_entries))
        self.assertTrue(any(not fe.is_archived for fe in feed_entries))

        self.assertGreater(
            feed.archive_update_backoff_until, now + datetime.timedelta(minutes=5)
        )

    # TODO write tests
