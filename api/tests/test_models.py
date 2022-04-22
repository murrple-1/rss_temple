import datetime
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone

from api.models import (
    User,
    UserCategory,
    SubscribedFeedUserMapping,
    Feed,
    VerificationToken,
    FeedEntry,
    ReadFeedEntryUserMapping,
)


class UserTestCase(TestCase):
    def test_create_user(self):
        User = get_user_model()
        user = User.objects.create_user(email="normal@user.com", password="password")
        self.assertEqual(user.email, "normal@user.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNone(user.username)
        with self.assertRaises(TypeError):
            User.objects.create_user()
        with self.assertRaises(TypeError):
            User.objects.create_user(email="")
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="foo")

    def test_create_superuser(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            email="super@user.com", password="password"
        )
        self.assertEqual(admin_user.email, "super@user.com")
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertIsNone(admin_user.username)
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="super@user.com", password="foo", is_superuser=False
            )

    def test_category_dict(self):
        user = User.objects.create_user("test_fields@test.com", "password")

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

        feed1.user_categories.add(user_category)

        category_dict = user.category_dict()

        self.assertIsInstance(category_dict, dict)
        self.assertEqual(len(category_dict), 2)
        self.assertIn(None, category_dict)
        self.assertIn(user_category.uuid, category_dict)
        self.assertIn(feed1, category_dict[user_category.uuid])
        self.assertIn(feed2, category_dict[None])


class VerificationTokenTestCase(TestCase):
    def test_token_str(self):
        verification_token = VerificationToken()

        self.assertIs(type(verification_token.token_str), str)

    def test_find_by_token(self):
        self.assertIsNone(VerificationToken.find_by_token("badtoken"))

        self.assertIsNone(VerificationToken.find_by_token(str(uuid.uuid4())))

        user = User.objects.create_user("test_fields@test.com", "password")

        verification_token = VerificationToken.objects.create(
            user=user,
            expires_at=timezone.now() + datetime.timedelta(days=1),
        )

        self.assertIsNotNone(
            VerificationToken.find_by_token(verification_token.token_str)
        )


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

    def test_counts(self):
        user = User.objects.create_user("test_fields@test.com", "password")

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
