import datetime

from django.test import TestCase

from api import models


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
