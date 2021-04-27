import datetime

from django.test import TestCase
from django.conf import settings

from api import archived_feed_entry_util, models


class ArchivedFeedEntryUtilTestCase(TestCase):
    def test_read_mapping_generator_fn(self):
        user = models.User.objects.create(email='test@test.com')

        feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed_entry = models.FeedEntry.objects.create(
            id=None,
            feed=feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)

        feed_entry.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1)
        feed_entry.save(update_fields=['published_at'])

        read_mappings = list(archived_feed_entry_util.read_mapping_generator_fn(feed, user))
        self.assertEqual(len(read_mappings), 1)

    def test_mark_archived_entries(self):
        self.assertEqual(models.ReadFeedEntryUserMapping.objects.all().count(), 0)

        user = models.User.objects.create(email='test@test.com')

        feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed_entry = models.FeedEntry.objects.create(
            id=None,
            feed=feed,
            created_at=None,
            updated_at=None,
            title='Feed Entry Title',
            url='http://example.com/entry.html',
            content='Some Entry content',
            author_name='John Doe',
            db_updated_at=None)

        feed_entry.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1)
        feed_entry.save(update_fields=['published_at'])

        archived_feed_entry_util.mark_archived_entries(archived_feed_entry_util.read_mapping_generator_fn(feed, user))

        self.assertEqual(models.ReadFeedEntryUserMapping.objects.all().count(), 1)
