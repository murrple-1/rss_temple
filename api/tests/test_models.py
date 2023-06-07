import datetime
import uuid

from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone

from api import models


class UserTestCase(TestCase):
    def test_category_dict(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        user_category = models.UserCategory.objects.create(user=user, text="Category")

        feed1 = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = models.Feed.objects.create(
            feed_url="http://example2.com/rss.xml",
            title="Sample Feed 2",
            home_url="http://example2.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        models.SubscribedFeedUserMapping.objects.create(feed=feed1, user=user)
        models.SubscribedFeedUserMapping.objects.create(feed=feed2, user=user)

        models.FeedUserCategoryMapping.objects.create(
            feed=feed1, user_category=user_category
        )

        category_dict = user.category_dict()

        self.assertIs(type(category_dict), dict)
        self.assertEqual(len(category_dict), 2)
        self.assertIn(None, category_dict)
        self.assertIn(user_category.uuid, category_dict)
        self.assertIn(feed1, category_dict[user_category.uuid])
        self.assertIn(feed2, category_dict[None])

    def test_subscribed_feeds_dict(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed1 = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = models.Feed.objects.create(
            feed_url="http://example2.com/rss.xml",
            title="Sample Feed 2",
            home_url="http://example2.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        models.SubscribedFeedUserMapping.objects.create(feed=feed1, user=user)
        models.SubscribedFeedUserMapping.objects.create(feed=feed2, user=user)

        subscribed_feeds_dict = user.subscribed_feeds_dict()

        self.assertIs(type(subscribed_feeds_dict), dict)
        self.assertEqual(len(subscribed_feeds_dict), 2)
        self.assertIn(feed1.uuid, subscribed_feeds_dict)
        self.assertIn(feed2.uuid, subscribed_feeds_dict)
        self.assertEqual(subscribed_feeds_dict[feed1.uuid], feed1)
        self.assertEqual(subscribed_feeds_dict[feed2.uuid], feed2)

    def test_read_feed_entry_mappings(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        models.ReadFeedEntryUserMapping.objects.create(feed_entry=feed_entry, user=user)

        self.assertEqual(user.read_feed_entry_mappings().count(), 1)

    def test_read_feed_entry_uuids(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        models.ReadFeedEntryUserMapping.objects.create(feed_entry=feed_entry, user=user)

        uuids = user.read_feed_entry_uuids()

        self.assertEqual(len(uuids), 1)
        self.assertIn(feed_entry.uuid, uuids)

    def test_favorite_feed_entry_mappings(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        models.FavoriteFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry, user=user
        )

        self.assertEqual(user.favorite_feed_entry_mappings().count(), 1)

    def test_favorite_feed_entry_uuids(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        models.FavoriteFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry, user=user
        )

        uuids = user.favorite_feed_entry_uuids()

        self.assertEqual(len(uuids), 1)
        self.assertIn(feed_entry.uuid, uuids)

    def test_google_login(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        self.assertIsNone(user.google_login())

        del user._google_login

        models.GoogleLogin.objects.create(user=user, g_user_id="googleid1")

        self.assertIsNotNone(user.google_login())

    def test_facebook_login(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        self.assertIsNone(user.facebook_login())

        del user._facebook_login

        models.FacebookLogin.objects.create(user=user, profile_id="facebookid")

        self.assertIsNotNone(user.facebook_login())


class VerificationTokenTestCase(TestCase):
    def test_token_str(self):
        verification_token = models.VerificationToken()

        self.assertIs(type(verification_token.token_str()), str)

    def test_find_by_token(self):
        self.assertIsNone(models.VerificationToken.find_by_token("badtoken"))

        self.assertIsNone(models.VerificationToken.find_by_token(str(uuid.uuid4())))

        user = models.User.objects.create_user("test_fields@test.com", None)

        verification_token = models.VerificationToken.objects.create(
            user=user,
            expires_at=timezone.now() + datetime.timedelta(days=1),
        )

        self.assertIsNotNone(
            models.VerificationToken.find_by_token(verification_token.token_str())
        )


class PasswordResetTokenTestCase(TestCase):
    def test_token_str(self):
        password_reset_token = models.PasswordResetToken()

        self.assertIs(type(password_reset_token.token_str()), str)

    def test_find_by_token(self):
        self.assertIsNone(models.PasswordResetToken.find_by_token("badtoken"))

        self.assertIsNone(models.PasswordResetToken.find_by_token(str(uuid.uuid4())))

        user = models.User.objects.create_user("test_fields@test.com", None)

        password_reset_token = models.PasswordResetToken.objects.create(
            user=user,
            expires_at=timezone.now() + datetime.timedelta(days=1),
        )

        self.assertIsNotNone(
            models.PasswordResetToken.find_by_token(password_reset_token.token_str())
        )


class UserCategoryTestCase(TestCase):
    def test_feeds(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        user_category = models.UserCategory.objects.create(user=user, text="Category")

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        models.FeedUserCategoryMapping.objects.create(
            feed=feed, user_category=user_category
        )

        self.assertEqual(user_category.feeds().count(), 1)


class FeedTestCase(TestCase):
    def test_with_subscription_data(self):
        feed = models.Feed(
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
        user = models.User.objects.create_user("test_fields@test.com", None)

        user_category = models.UserCategory.objects.create(user=user, text="Category")

        feed1 = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = models.Feed.objects.create(
            feed_url="http://example2.com/rss.xml",
            title="Sample Feed 2",
            home_url="http://example2.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        models.SubscribedFeedUserMapping.objects.create(feed=feed1, user=user)
        models.SubscribedFeedUserMapping.objects.create(feed=feed2, user=user)

        models.FeedUserCategoryMapping.objects.create(
            feed=feed1, user_category=user_category
        )

        self.assertEqual(feed1.user_categories(user).count(), 1)
        self.assertEqual(feed2.user_categories(user).count(), 0)

    def test_feed_entries(self):
        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        self.assertEqual(feed.feed_entries().count(), 1)

    def test_counts(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        read_feed_entry = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        models.ReadFeedEntryUserMapping.objects.create(
            feed_entry=read_feed_entry, user=user
        )

        self.assertEqual(feed.unread_count(user), 1)
        self.assertEqual(feed.read_count(user), 1)


class FeedEntryTestCase(TestCase):
    def test_eq(self):
        feed = models.Feed(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = models.FeedEntry(
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

        feed_entry2 = models.FeedEntry(
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
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed1 = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed2 = models.Feed.objects.create(
            feed_url="http://example2.com/rss.xml",
            title="Sample Feed 2",
            home_url="http://example2.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = models.FeedEntry.objects.create(
            feed=feed1,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        feed_entry2 = models.FeedEntry.objects.create(
            feed=feed2,
            url="http://example2.com/entry.html",
            content="<b>Some HTML Content</b>",
            author_name="Jane Doe",
        )

        models.SubscribedFeedUserMapping.objects.create(feed=feed2, user=user)

        self.assertFalse(feed_entry1.from_subscription(user))
        self.assertTrue(feed_entry2.from_subscription(user))

    def test_is_read(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        feed_entry2 = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        models.ReadFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry2, user=user
        )

        self.assertFalse(feed_entry1.is_read(user))
        self.assertTrue(feed_entry2.is_read(user))

    def test_is_favorite(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        feed_entry2 = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        models.FavoriteFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry2, user=user
        )

        self.assertFalse(feed_entry1.is_favorite(user))
        self.assertTrue(feed_entry2.is_favorite(user))

    def test_read_mapping(self):
        user = models.User.objects.create_user("test_fields@test.com", None)

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        feed_entry2 = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        models.ReadFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry2, user=user
        )

        self.assertIsNone(feed_entry1.read_mapping(user))
        self.assertIsNotNone(feed_entry2.read_mapping(user))

    def test_unique_feed_url_updated_at(self):
        now = timezone.now()

        feed = models.Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = models.FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
            updated_at=None,
        )

        feed_entry2 = models.FeedEntry.objects.create(
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
                models.FeedEntry.objects.create(
                    feed=feed,
                    url="http://example.com/entry1.html",
                    content="<b>Some HTML Content</b>",
                    author_name="John Doe",
                    updated_at=now,
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                models.FeedEntry.objects.create(
                    feed=feed,
                    url="http://example.com/entry1.html",
                    content="<b>Some HTML Content</b>",
                    author_name="John Doe",
                    updated_at=None,
                )

        feed_entry3 = models.FeedEntry.objects.create(
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
