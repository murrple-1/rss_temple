import datetime
import itertools
import logging
from typing import ClassVar

from django.test import TestCase
from django.utils import timezone

from api.models import Feed, FeedEntry
from api.tasks.find_duplicate_feeds import are_feeds_duplicate, find_duplicate_feeds


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

    def _generate_feeds(self) -> tuple[list[Feed], list[Feed]]:
        now = timezone.now()

        def feed_url_fn(i: int) -> str:
            return f"http://example.com/rss{i}.xml"

        def entry_content_fn(i: int) -> str:
            return f"Some Entry content for {i}"

        def same_title_fn() -> str:
            return "Sample Feed"

        def same_home_url_fn() -> str:
            return "http://example.com"

        def same_entry_title_fn(i: int) -> str:
            return f"Feed Entry Title {i}"

        def same_entry_url_fn(i: int) -> str:
            return f"http://example.com/entry{i}.html"

        same_feed_count = 2

        same_feeds: list[Feed] = []
        for i in range(same_feed_count):
            feed = Feed.objects.create(
                feed_url=feed_url_fn(i),
                title=same_title_fn(),
                home_url=same_home_url_fn(),
                published_at=now + datetime.timedelta(days=-1),
                updated_at=None,
                db_updated_at=None,
            )

            FeedEntry.objects.bulk_create(
                FeedEntry(
                    feed=feed,
                    published_at=now + datetime.timedelta(days=-j),
                    title=same_entry_title_fn(j),
                    url=same_entry_url_fn(j),
                    content=entry_content_fn(j),
                    author_name="John Doe",
                    db_updated_at=None,
                    is_archived=False,
                )
                for j in range(1, 20, 1)
            )

            same_feeds.append(feed)

        def different_title_fn() -> str:
            return "Different Sample Feed"

        def different_home_url_fn() -> str:
            return "http://different.com"

        def different_entry_title_fn(i: int) -> str:
            return f"DifferentFeed Entry Title {i}"

        def different_entry_url_fn(i: int) -> str:
            return f"http://different.com/entry{i}.html"

        different_feeds: list[Feed] = []
        for i, (title_fn, home_url_fn, entry_title_fn, entry_url_fn) in enumerate(
            [
                (
                    different_title_fn,
                    same_home_url_fn,
                    same_entry_title_fn,
                    same_entry_url_fn,
                ),
                (
                    same_title_fn,
                    different_home_url_fn,
                    same_entry_title_fn,
                    same_entry_url_fn,
                ),
                (
                    same_title_fn,
                    same_home_url_fn,
                    different_entry_title_fn,
                    same_entry_url_fn,
                ),
                (
                    same_title_fn,
                    same_home_url_fn,
                    same_entry_title_fn,
                    different_entry_url_fn,
                ),
            ]
        ):
            feed = Feed.objects.create(
                feed_url=feed_url_fn(i + same_feed_count),
                title=title_fn(),
                home_url=home_url_fn(),
                published_at=now + datetime.timedelta(days=-1),
                updated_at=None,
                db_updated_at=None,
            )

            FeedEntry.objects.bulk_create(
                FeedEntry(
                    feed=feed,
                    published_at=now + datetime.timedelta(days=-i),
                    title=entry_title_fn(i),
                    url=entry_url_fn(i),
                    content=f"Some Entry content for {i}",
                    author_name="John Doe",
                    db_updated_at=None,
                    is_archived=False,
                )
                for i in range(1, 20, 1)
            )

            different_feeds.append(feed)

        return same_feeds, different_feeds

    def test_find_duplicate_feeds(self):
        same_feeds, different_feeds = self._generate_feeds()

        duplicate_feeds = find_duplicate_feeds(10, 10, 1)

        self.assertEqual(len(duplicate_feeds), 1)

        ((duplicate_feed1, duplicate_feed2),) = duplicate_feeds

        self.assertIn(duplicate_feed1.uuid, [sf.uuid for sf in same_feeds])
        self.assertIn(duplicate_feed2.uuid, [sf.uuid for sf in same_feeds])

        for different_feed in different_feeds:
            self.assertNotEqual(duplicate_feed1.uuid, different_feed.uuid)
            self.assertNotEqual(duplicate_feed2.uuid, different_feed.uuid)

    def test_are_feeds_duplicate(self):
        same_feeds, different_feeds = self._generate_feeds()

        self.assertEqual(len(same_feeds), 2)

        same_feed1, same_feed2 = same_feeds

        self.assertIsNotNone(are_feeds_duplicate(same_feed1, same_feed2, 10, 1))

        for different_feed in different_feeds:
            self.assertIsNone(are_feeds_duplicate(different_feed, same_feed1, 10, 1))
            self.assertIsNone(are_feeds_duplicate(different_feed, same_feed2, 10, 1))

        for different_feed1, different_feed2 in itertools.combinations(
            different_feeds, 2
        ):
            self.assertIsNone(
                are_feeds_duplicate(different_feed1, different_feed2, 10, 1)
            )
