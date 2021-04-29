import datetime

from django.test import TestCase

from api import models


# TODO a whole bunch more tests are needed here
class FeedEntryTestCase(TestCase):
    def test_eq(self):
        feed = models.Feed(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed_entry1 = models.FeedEntry(
            id=None,
            feed=feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 1 Title',
            url='http://example.com/entry1.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)

        feed_entry2 = models.FeedEntry(
            id=None,
            feed=feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry 2 Title',
            url='http://example.com/entry2.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)

        self.assertTrue(feed_entry1 == feed_entry1)

        self.assertFalse(feed_entry1 == feed_entry2)

        self.assertFalse(feed_entry1 == object())

    def test_from_subscription(self):
        user = models.User.objects.create(
            email='test_fields@test.com')

        feed1 = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed2 = models.Feed.objects.create(
            feed_url='http://example2.com/rss.xml',
            title='Sample Feed 2',
            home_url='http://example2.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed_entry1 = models.FeedEntry.objects.create(
            feed=feed1,
            url='http://example.com/entry1.html',
            content='<b>Some HTML Content</b>',
            author_name='John Doe')
        feed_entry2 = models.FeedEntry.objects.create(
            feed=feed2,
            url='http://example2.com/entry.html',
            content='<b>Some HTML Content</b>',
            author_name='Jane Doe')

        models.SubscribedFeedUserMapping.objects.create(feed=feed2, user=user)

        self.assertFalse(feed_entry1.from_subscription(user))
        self.assertTrue(feed_entry2.from_subscription(user))

    def test_is_read(self):
        user = models.User.objects.create(
            email='test_fields@test.com')

        feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed_entry1 = models.FeedEntry.objects.create(
            feed=feed,
            url='http://example.com/entry1.html',
            content='<b>Some HTML Content</b>',
            author_name='John Doe')
        feed_entry2 = models.FeedEntry.objects.create(
            feed=feed,
            url='http://example.com/entry2.html',
            content='<b>Some HTML Content</b>',
            author_name='John Doe')

        models.ReadFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry2, user=user)

        self.assertFalse(feed_entry1.is_read(user))
        self.assertTrue(feed_entry2.is_read(user))
