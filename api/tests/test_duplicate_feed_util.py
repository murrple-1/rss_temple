from typing import ClassVar

from django.test import TestCase
from django.utils import timezone

from api.duplicate_feed_util import (
    DuplicateFeedTuple,
    convert_duplicate_feeds_to_alternate_feed_urls,
)
from api.models import Feed, FeedEntry, ReadFeedEntryUserMapping, User, UserCategory


class DuplicateFeedUtilTestCase(TestCase):
    user: ClassVar[User]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test@test.com", None)

    def test_convert_duplicate_feeds_to_alternate_feed_urls(self):
        user_category = UserCategory.objects.create(
            user=DuplicateFeedUtilTestCase.user, text="My Category"
        )

        feed1 = Feed.objects.create(
            feed_url="http://example.com/rss1.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url="http://example.com/rss2.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        DuplicateFeedUtilTestCase.user.subscribed_feeds.add(feed1)

        user_category.feeds.add(feed1)

        feed1_entry1 = FeedEntry.objects.create(
            id=None,
            feed=feed1,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        feed2_entry1 = FeedEntry.objects.create(
            id=None,
            feed=feed2,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        ReadFeedEntryUserMapping.objects.create(
            user=DuplicateFeedUtilTestCase.user, feed_entry=feed1_entry1
        )
        DuplicateFeedUtilTestCase.user.favorite_feed_entries.add(feed1_entry1)

        convert_duplicate_feeds_to_alternate_feed_urls(
            [DuplicateFeedTuple(feed2, feed1)]
        )

        self.assertFalse(Feed.objects.filter(uuid=feed1.uuid).exists())
        self.assertTrue(user_category.feeds.filter(uuid=feed2.uuid).exists())
        self.assertTrue(
            DuplicateFeedUtilTestCase.user.subscribed_feeds.filter(
                uuid=feed2.uuid
            ).exists()
        )
        self.assertFalse(
            ReadFeedEntryUserMapping.objects.filter(
                user=DuplicateFeedUtilTestCase.user, feed_entry_id=feed1_entry1.uuid
            ).exists()
        )
        self.assertTrue(
            ReadFeedEntryUserMapping.objects.filter(
                user=DuplicateFeedUtilTestCase.user, feed_entry_id=feed2_entry1.uuid
            ).exists()
        )
        self.assertTrue(
            DuplicateFeedUtilTestCase.user.favorite_feed_entries.filter(
                uuid=feed2_entry1.uuid
            ).exists()
        )

    def test_convert_duplicate_feeds_to_alternate_feed_urls_subscribedtoboth(self):
        feed1 = Feed.objects.create(
            feed_url="http://example.com/rss1.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url="http://example.com/rss2.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        DuplicateFeedUtilTestCase.user.subscribed_feeds.add(feed1, feed2)

        convert_duplicate_feeds_to_alternate_feed_urls(
            [DuplicateFeedTuple(feed2, feed1)]
        )

    def test_convert_duplicate_feeds_to_alternate_feed_urls_readbothentries(self):
        feed1 = Feed.objects.create(
            feed_url="http://example.com/rss1.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url="http://example.com/rss2.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed1_entry1 = FeedEntry.objects.create(
            id=None,
            feed=feed1,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        feed2_entry1 = FeedEntry.objects.create(
            id=None,
            feed=feed2,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        DuplicateFeedUtilTestCase.user.read_feed_entries.add(feed1_entry1, feed2_entry1)

        convert_duplicate_feeds_to_alternate_feed_urls(
            [DuplicateFeedTuple(feed2, feed1)]
        )

    def test_convert_duplicate_feeds_to_alternate_feed_urls_favoritedbothentries(self):
        feed1 = Feed.objects.create(
            feed_url="http://example.com/rss1.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url="http://example.com/rss2.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed1_entry1 = FeedEntry.objects.create(
            id=None,
            feed=feed1,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        feed2_entry1 = FeedEntry.objects.create(
            id=None,
            feed=feed2,
            created_at=None,
            updated_at=None,
            title="Feed Entry Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        DuplicateFeedUtilTestCase.user.favorite_feed_entries.add(
            feed1_entry1, feed2_entry1
        )

        convert_duplicate_feeds_to_alternate_feed_urls(
            [DuplicateFeedTuple(feed2, feed1)]
        )

    def test_convert_duplicate_feeds_to_alternate_feed_urls_bothincategories(self):
        user_category = UserCategory.objects.create(
            user=DuplicateFeedUtilTestCase.user, text="My Category"
        )

        feed1 = Feed.objects.create(
            feed_url="http://example.com/rss1.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url="http://example.com/rss2.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        user_category.feeds.add(feed1, feed2)

        convert_duplicate_feeds_to_alternate_feed_urls(
            [DuplicateFeedTuple(feed2, feed1)]
        )

        self.assertTrue(user_category.feeds.filter(uuid=feed2.uuid).exists())
