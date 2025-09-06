import datetime
import logging
from typing import ClassVar

from django.test import tag
from django.utils import timezone

from api.models import Feed, FeedEntry
from api.tasks.extract_top_images import extract_top_images
from api.tests import TestFileServerTestCase
from api.tests.utils import generate_top_image_pages


class TaskTestCase(TestFileServerTestCase):
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

    @tag("slow")
    def test_extract_top_images(self):
        now = timezone.now()

        feed = Feed.objects.create(
            feed_url=f"{TaskTestCase.live_server_url}/rss.xml",
            title="Sample Feed",
            home_url=TaskTestCase.live_server_url,
            published_at=now + datetime.timedelta(days=-1),
            updated_at=None,
            db_updated_at=None,
        )

        for i, url, lang, title, content in generate_top_image_pages(
            TaskTestCase.live_server_url
        ):
            FeedEntry.objects.create(
                feed=feed,
                published_at=now + datetime.timedelta(days=-i),
                title=title,
                url=url,
                content=content,
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
                language_id=lang,
            )

        FeedEntry.objects.create(
            feed=feed,
            published_at=now + datetime.timedelta(days=-100),
            title="Title",
            url=f"{TaskTestCase.live_server_url}/site/entry_notexist.html",
            content="<p>Content</p>",
            author_name="John Doe",
            db_updated_at=None,
            is_archived=False,
        )

        count = extract_top_images(
            FeedEntry.objects.select_related("language").all(), 3, 2000, 256, 256, -1, 5
        )

        self.assertEqual(
            FeedEntry.objects.filter(has_top_image_been_processed=False).count(), 0
        )
        self.assertEqual(
            FeedEntry.objects.filter(has_top_image_been_processed=True).count(), count
        )
        self.assertGreater(FeedEntry.objects.filter(top_image_src="").count(), 0)
        self.assertLess(
            FeedEntry.objects.filter(top_image_src="").count(),
            FeedEntry.objects.count(),
        )
        self.assertEqual(
            FeedEntry.objects.exclude(top_image_processing_attempt_count=0).count(),
            0,
        )
