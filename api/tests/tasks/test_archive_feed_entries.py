import datetime
import logging
from typing import ClassVar

from django.test import TestCase
from django.utils import timezone

from api.models import Feed, FeedEntry
from api.tasks.archive_feed_entries import archive_feed_entries


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

    def test_archive_feed_entries(self):
        now = timezone.now()

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

        archive_feed_entries(feed, now, datetime.timedelta(days=-30), 5, 60 * 60 * 24)

        for feed_entry in feed_entries:
            feed_entry.refresh_from_db()

        feed.refresh_from_db()

        self.assertTrue(any(fe.is_archived for fe in feed_entries))
        self.assertTrue(any(not fe.is_archived for fe in feed_entries))

        self.assertGreater(
            feed.archive_update_backoff_until, now + datetime.timedelta(minutes=5)
        )

    # TODO write tests
