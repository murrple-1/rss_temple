from typing import ClassVar
import uuid
import logging

from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import Feed, FeedEntry, FeedEntryReport, FeedReport, User
from api.tests.utils import (
    disable_silk,
    disable_throttling,
)


@disable_silk()
@disable_throttling()
class ReportTestCase(APITestCase):
    old_django_logger_level: ClassVar[int]
    user: ClassVar[User]
    feed: ClassVar[Feed]
    feed_entry: ClassVar[FeedEntry]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("django").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test@test.com", None)

        cls.feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        cls.feed_entry = FeedEntry.objects.create(
            id=None,
            feed=cls.feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

    def setUp(self):
        super().setUp()

        self.client.force_authenticate(user=ReportTestCase.user)

    def test_FeedReportView_post(self):
        self.assertEqual(FeedReport.objects.filter(feed=ReportTestCase.feed).count(), 0)

        response = self.client.post(
            "/api/report/feed",
            {
                "feedUuid": str(ReportTestCase.feed.uuid),
                "reason": "Test Reason",
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(FeedReport.objects.filter(feed=ReportTestCase.feed).count(), 1)

    def test_FeedReportView_post_notfound(self):
        response = self.client.post(
            "/api/report/feed",
            {
                "feedUuid": str(uuid.UUID(int=0)),
                "reason": "Test Reason",
            },
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_FeedEntryReportView_post(self):
        self.assertEqual(
            FeedEntryReport.objects.filter(
                feed_entry=ReportTestCase.feed_entry
            ).count(),
            0,
        )

        response = self.client.post(
            "/api/report/feedentry",
            {
                "feedEntryUuid": str(ReportTestCase.feed_entry.uuid),
                "reason": "Test Reason",
            },
        )
        self.assertEqual(response.status_code, 204, response.content)

        self.assertEqual(
            FeedEntryReport.objects.filter(
                feed_entry=ReportTestCase.feed_entry
            ).count(),
            1,
        )

    def test_FeedEntryReportView_post_notfound(self):
        response = self.client.post(
            "/api/report/feedentry",
            {
                "feedEntryUuid": str(uuid.UUID(int=0)),
                "reason": "Test Reason",
            },
        )
        self.assertEqual(response.status_code, 404, response.content)
