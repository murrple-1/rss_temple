from unittest.mock import Mock

from django.forms import BaseFormSet
from django.http import HttpRequest, HttpResponse
from django.test import TestCase
from django.utils import timezone

from api.admin import remove_feeds_util
from api.models import (
    AlternateFeedURL,
    Feed,
    FeedEntry,
    FeedEntryReport,
    FeedReport,
    RemovedFeed,
)


class RemoveFeedsUtilTestCase(TestCase):
    def _generate_feed_and_entry(
        self, home_url="http://test.com"
    ) -> tuple[Feed, FeedEntry]:
        feed = Feed.objects.create(
            feed_url=f"{home_url}/rss.xml",
            title="Sample Feed",
            home_url=home_url,
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry = FeedEntry.objects.create(
            id=None,
            feed=feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url=f"{home_url}/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        return feed, feed_entry

    def test_generate_formset(self):
        self.assertIsInstance(
            remove_feeds_util.generate_formset(Feed.objects.all(), query_post=None),
            BaseFormSet,
        )

        feed, feed_entry = self._generate_feed_and_entry()

        self.assertIsInstance(
            remove_feeds_util.generate_formset(Feed.objects.all(), query_post=None),
            BaseFormSet,
        )

        FeedReport.objects.create(feed=feed, reason="Test Feed Reason")

        FeedEntryReport.objects.create(
            feed_entry=feed_entry, reason="Test Feed Entry Reason"
        )

        self.assertIsInstance(
            remove_feeds_util.generate_formset(Feed.objects.all(), query_post=None),
            BaseFormSet,
        )

    def test_render(self):
        request = Mock(HttpRequest)
        request.META = {}
        response1 = remove_feeds_util.render(
            request,
            remove_feeds_util.generate_formset(Feed.objects.all(), query_post=None),
            [],
        )
        self.assertIsInstance(response1, HttpResponse)

        feed, feed_entry = self._generate_feed_and_entry()

        request = Mock(HttpRequest)
        request.META = {}
        response2 = remove_feeds_util.render(
            request,
            remove_feeds_util.generate_formset(Feed.objects.all(), query_post=None),
            [],
        )
        self.assertIsInstance(response2, HttpResponse)

        FeedReport.objects.create(feed=feed, reason="Test Feed Reason")

        FeedEntryReport.objects.create(
            feed_entry=feed_entry, reason="Test Feed Entry Reason"
        )

        response3 = remove_feeds_util.render(
            request,
            remove_feeds_util.generate_formset(Feed.objects.all(), query_post=None),
            [],
        )
        self.assertIsInstance(response3, HttpResponse)

        self.assertNotEqual(response1.content, response2.content)
        self.assertNotEqual(response1.content, response3.content)
        self.assertNotEqual(response2.content, response3.content)

    def test_remove_feeds(self):
        self.assertEqual(Feed.objects.count(), 0)
        self.assertEqual(FeedEntry.objects.count(), 0)
        self.assertEqual(RemovedFeed.objects.count(), 0)

        remove_feeds_util.remove_feeds({})

        self.assertEqual(Feed.objects.count(), 0)
        self.assertEqual(AlternateFeedURL.objects.count(), 0)
        self.assertEqual(FeedEntry.objects.count(), 0)
        self.assertEqual(RemovedFeed.objects.count(), 0)

        feed1, _ = self._generate_feed_and_entry(home_url="http://test1.com")

        self.assertEqual(Feed.objects.count(), 1)
        self.assertEqual(AlternateFeedURL.objects.count(), 0)
        self.assertEqual(FeedEntry.objects.count(), 1)
        self.assertEqual(RemovedFeed.objects.count(), 0)

        remove_feeds_util.remove_feeds({})

        self.assertEqual(Feed.objects.count(), 1)
        self.assertEqual(AlternateFeedURL.objects.count(), 0)
        self.assertEqual(FeedEntry.objects.count(), 1)
        self.assertEqual(RemovedFeed.objects.count(), 0)

        remove_feeds_util.remove_feeds({feed1.uuid: "Reason 1"})

        self.assertEqual(Feed.objects.count(), 0)
        self.assertEqual(AlternateFeedURL.objects.count(), 0)
        self.assertEqual(FeedEntry.objects.count(), 0)
        self.assertEqual(RemovedFeed.objects.count(), 1)

        feed2, _ = self._generate_feed_and_entry(home_url="http://test2.com")
        AlternateFeedURL.objects.create(
            feed=feed2, feed_url=f"{feed2.feed_url}?param=value"
        )

        self.assertEqual(Feed.objects.count(), 1)
        self.assertEqual(AlternateFeedURL.objects.count(), 1)
        self.assertEqual(FeedEntry.objects.count(), 1)
        self.assertEqual(RemovedFeed.objects.count(), 1)

        remove_feeds_util.remove_feeds({feed2.uuid: "Reason 2"})

        self.assertEqual(Feed.objects.count(), 0)
        self.assertEqual(AlternateFeedURL.objects.count(), 0)
        self.assertEqual(FeedEntry.objects.count(), 0)
        self.assertEqual(RemovedFeed.objects.count(), 3)

        reasons: frozenset[str] = frozenset(
            RemovedFeed.objects.values_list("reason", flat=True)
        )

        self.assertIn("Reason 1", reasons)
        self.assertIn("Reason 2", reasons)
        self.assertIn("duplicate of http://test2.com/rss.xml\n---\nReason 2", reasons)
