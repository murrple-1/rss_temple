import datetime
import random

from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone

from api.models import (
    Captcha,
    Feed,
    FeedEntry,
    ReadFeedEntryUserMapping,
    SubscribedFeedUserMapping,
    User,
    UserCategory,
)
from api.tests.utils import reusable_captcha_key, reusable_captcha_seed


class UserTestCase(TestCase):
    def test_create_user(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("", "password")

    def test_create_superuser(self):
        User.objects.create_superuser("test@test.com", "password")

        with self.assertRaises(ValueError):
            User.objects.create_superuser("test1@test.com", "password", is_staff=False)

        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                "test2@test.com", "password", is_superuser=False
            )

    def test_category_dict(self):
        user = User.objects.create_user("test_fields@test.com", None)

        user_category = UserCategory.objects.create(user=user, text="Category")

        feed1 = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url="http://example2.com/rss.xml",
            title="Sample Feed 2",
            home_url="http://example2.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(feed=feed1, user=user)
        SubscribedFeedUserMapping.objects.create(feed=feed2, user=user)

        user_category.feeds.add(feed1)

        category_dict = user.category_dict()

        self.assertIsInstance(category_dict, dict)
        self.assertEqual(len(category_dict), 2)
        self.assertIn(None, category_dict)
        self.assertIn(user_category.uuid, category_dict)
        self.assertIn(feed1, category_dict[user_category.uuid])
        self.assertIn(feed2, category_dict[None])

    def test_favorite_feed_entry_mappings(self):
        user = User.objects.create_user("test_fields@test.com", None)

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        user.favorite_feed_entries.add(feed_entry)

        self.assertEqual(user.favorite_feed_entries.count(), 1)

    def test_favorite_feed_entry_uuids(self):
        user = User.objects.create_user("test_fields@test.com", None)

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        user.favorite_feed_entries.add(feed_entry)

        uuids = list(user.favorite_feed_entries.values_list("uuid", flat=True))

        self.assertEqual(len(uuids), 1)
        self.assertIn(feed_entry.uuid, uuids)


class UserCategoryTestCase(TestCase):
    def test_feeds(self):
        user = User.objects.create_user("test_fields@test.com", None)

        user_category = UserCategory.objects.create(user=user, text="Category")

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        user_category.feeds.add(feed)

        self.assertEqual(user_category.feeds.count(), 1)

    def test_str(self):
        user_category = UserCategory(text="Category")

        self.assertEqual(str(user_category), "Category")


class FeedTestCase(TestCase):
    def test_with_subscription_data(self):
        feed = Feed(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        self.assertFalse(hasattr(feed, "custom_title"))
        self.assertFalse(hasattr(feed, "is_subscribed"))

        feed.with_subscription_data()

        self.assertTrue(hasattr(feed, "custom_title"))
        self.assertTrue(hasattr(feed, "is_subscribed"))

    def test_user_categories(self):
        user = User.objects.create_user("test_fields@test.com", None)

        user_category = UserCategory.objects.create(user=user, text="Category")

        feed1 = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url="http://example2.com/rss.xml",
            title="Sample Feed 2",
            home_url="http://example2.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        SubscribedFeedUserMapping.objects.create(feed=feed1, user=user)
        SubscribedFeedUserMapping.objects.create(feed=feed2, user=user)

        user_category.feeds.add(feed1)

        self.assertEqual(user_category.feeds.filter(uuid=feed1.uuid).count(), 1)
        self.assertEqual(user_category.feeds.filter(uuid=feed2.uuid).count(), 0)

    def test_feed_entries(self):
        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        self.assertEqual(feed.feed_entries.count(), 1)

    def test_counts(self):
        user = User.objects.create_user("test_fields@test.com", None)

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        read_feed_entry = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        ReadFeedEntryUserMapping.objects.create(feed_entry=read_feed_entry, user=user)

        self.assertEqual(feed.unread_count(user), 1)
        self.assertEqual(feed.read_count(user), 1)

    def test_str(self):
        feed = Feed(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        self.assertEqual(
            str(feed), f"Sample Feed - http://example.com/rss.xml - {feed.uuid}"
        )


class FeedEntryTestCase(TestCase):
    def test_eq(self):
        feed = Feed(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = FeedEntry(
            id=None,
            feed=feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 1 Title",
            url="http://example.com/entry1.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        feed_entry2 = FeedEntry(
            id=None,
            feed=feed,
            created_at=None,
            updated_at=None,
            title="Feed Entry 2 Title",
            url="http://example.com/entry2.html",
            content="Some Entry content",
            author_name="John Doe",
            db_updated_at=None,
        )

        self.assertTrue(feed_entry1 == feed_entry1)

        self.assertFalse(feed_entry1 == feed_entry2)

        self.assertFalse(feed_entry1 == object())

    def test_from_subscription(self):
        user = User.objects.create_user("test_fields@test.com", None)

        feed1 = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = Feed.objects.create(
            feed_url="http://example2.com/rss.xml",
            title="Sample Feed 2",
            home_url="http://example2.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = FeedEntry.objects.create(
            feed=feed1,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        feed_entry2 = FeedEntry.objects.create(
            feed=feed2,
            url="http://example2.com/entry.html",
            content="<b>Some HTML Content</b>",
            author_name="Jane Doe",
        )

        SubscribedFeedUserMapping.objects.create(feed=feed2, user=user)

        self.assertFalse(feed_entry1.from_subscription(user))
        self.assertTrue(feed_entry2.from_subscription(user))

    def test_is_read(self):
        user = User.objects.create_user("test_fields@test.com", None)

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        feed_entry2 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        ReadFeedEntryUserMapping.objects.create(feed_entry=feed_entry2, user=user)

        self.assertFalse(feed_entry1.is_read(user))
        self.assertTrue(feed_entry2.is_read(user))

    def test_is_favorite(self):
        user = User.objects.create_user("test_fields@test.com", None)

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        feed_entry2 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        user.favorite_feed_entries.add(feed_entry2)

        self.assertFalse(feed_entry1.is_favorite(user))
        self.assertTrue(feed_entry2.is_favorite(user))

    def test_read_mapping(self):
        user = User.objects.create_user("test_fields@test.com", None)

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        feed_entry2 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        ReadFeedEntryUserMapping.objects.create(feed_entry=feed_entry2, user=user)

        self.assertIsNone(feed_entry1.read_user_set.filter(uuid=user.uuid).first())
        self.assertIsNotNone(feed_entry2.read_user_set.filter(uuid=user.uuid).first())

    def test_unique_feed_url_updated_at(self):
        now = timezone.now()

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
            updated_at=None,
        )

        feed_entry2 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
            updated_at=now,
        )

        feed_entry2.updated_at = None
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                feed_entry2.save(update_fields=["updated_at"])

        feed_entry2.refresh_from_db()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FeedEntry.objects.create(
                    feed=feed,
                    url="http://example.com/entry1.html",
                    content="<b>Some HTML Content</b>",
                    author_name="John Doe",
                    updated_at=now,
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FeedEntry.objects.create(
                    feed=feed,
                    url="http://example.com/entry1.html",
                    content="<b>Some HTML Content</b>",
                    author_name="John Doe",
                    updated_at=None,
                )

        feed_entry3 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
            updated_at=now + datetime.timedelta(hours=1),
        )

        feed_entry3.updated_at = now
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                feed_entry3.save(update_fields=["updated_at"])

        feed_entry3.refresh_from_db()

        self.assertEqual(feed_entry1.feed_id, feed_entry2.feed_id)
        self.assertEqual(feed_entry2.feed_id, feed_entry3.feed_id)

        self.assertEqual(feed_entry1.url, feed_entry2.url)
        self.assertEqual(feed_entry2.url, feed_entry3.url)

        self.assertNotEqual(feed_entry1.updated_at, feed_entry2.updated_at)
        self.assertNotEqual(feed_entry2.updated_at, feed_entry3.updated_at)
        self.assertNotEqual(feed_entry1.updated_at, feed_entry3.updated_at)

    def test_str(self):
        feed_entry = FeedEntry(
            url="http://example.com/entry1.html",
            title="Title",
        )

        self.assertEqual(str(feed_entry), "Title - http://example.com/entry1.html")


class CaptchaTestCase(TestCase):
    def _generate_captcha(self):
        return Captcha(
            key=reusable_captcha_key(),
            seed=reusable_captcha_seed(),
            expires_at=(timezone.now() + datetime.timedelta(minutes=5)),
        )

    def test_rng(self):
        captcha = self._generate_captcha()
        self.assertIs(type(captcha.rng), random.Random)

    def test_secret_phrase(self):
        captcha = self._generate_captcha()
        self.assertEqual(captcha.secret_phrase, "649290")
