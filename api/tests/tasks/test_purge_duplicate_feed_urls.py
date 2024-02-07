import datetime
import logging
from typing import ClassVar

from django.test import TestCase
from django.utils import timezone

from api.models import AlternateFeedURL, Feed
from api.tasks.purge_duplicate_feed_urls import purge_duplicate_feed_urls


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

    def test_purge_duplicate_feed_urls(self):
        now = timezone.now()

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=now + datetime.timedelta(days=-1),
            updated_at=None,
            db_updated_at=None,
        )
        AlternateFeedURL.objects.create(
            feed=feed, feed_url="http://example.com/rss.xml"
        )
        AlternateFeedURL.objects.create(
            feed=feed, feed_url="https://example.com/rss.xml"
        )

        self.assertEqual(AlternateFeedURL.objects.count(), 2)

        purge_duplicate_feed_urls()

        self.assertEqual(AlternateFeedURL.objects.count(), 1)
