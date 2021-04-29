import datetime

from django.test import TestCase
from django.conf import settings

from api import archived_feed_entry_util, models


class ArchivedFeedEntryUtilTestCase(TestCase):
    def test_read_mapping_generator_fn_morethanmincount(self):
        with self.settings(USER_UNREAD_GRACE_INTERVAL=datetime.timedelta(days=-7), USER_UNREAD_GRACE_MIN_COUNT=1):
            user = models.User.objects.create(email='test@test.com')

            feed = models.Feed.objects.create(
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

            feed_entry3 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 3 Title',
                url='http://example.com/entry3.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            feed_entry4 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 4 Title',
                url='http://example.com/entry4.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            models.FeedEntry.objects.bulk_create([feed_entry1, feed_entry2, feed_entry3, feed_entry4])

            feed_entry1.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-10)
            feed_entry1.save(update_fields=['published_at'])

            feed_entry2.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-20)
            feed_entry2.save(update_fields=['published_at'])

            read_mappings = list(archived_feed_entry_util.read_mapping_generator_fn(feed, user))
            self.assertEqual(len(read_mappings), 2)

    def test_read_mapping_generator_fn_equalmincount(self):
        with self.settings(USER_UNREAD_GRACE_INTERVAL=datetime.timedelta(days=-7), USER_UNREAD_GRACE_MIN_COUNT=2):
            user = models.User.objects.create(email='test@test.com')

            feed = models.Feed.objects.create(
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

            feed_entry3 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 3 Title',
                url='http://example.com/entry3.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            feed_entry4 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 4 Title',
                url='http://example.com/entry4.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            models.FeedEntry.objects.bulk_create([feed_entry1, feed_entry2, feed_entry3, feed_entry4])

            feed_entry1.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-10)
            feed_entry1.save(update_fields=['published_at'])

            feed_entry2.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-20)
            feed_entry2.save(update_fields=['published_at'])

            read_mappings = list(archived_feed_entry_util.read_mapping_generator_fn(feed, user))
            self.assertEqual(len(read_mappings), 2)

    def test_read_mapping_generator_fn_lessthanmincount(self):
        with self.settings(USER_UNREAD_GRACE_INTERVAL=datetime.timedelta(days=-7), USER_UNREAD_GRACE_MIN_COUNT=5):
            user = models.User.objects.create(email='test@test.com')

            feed = models.Feed.objects.create(
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

            feed_entry3 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 3 Title',
                url='http://example.com/entry3.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            feed_entry4 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 4 Title',
                url='http://example.com/entry4.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            models.FeedEntry.objects.bulk_create([feed_entry1, feed_entry2, feed_entry3, feed_entry4])

            feed_entry1.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-10)
            feed_entry1.save(update_fields=['published_at'])

            feed_entry2.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-20)
            feed_entry2.save(update_fields=['published_at'])

            read_mappings = list(archived_feed_entry_util.read_mapping_generator_fn(feed, user))
            self.assertEqual(len(read_mappings), 0)

    def test_mark_archived_entries_morethanmincount(self):
        with self.settings(USER_UNREAD_GRACE_INTERVAL=datetime.timedelta(days=-7), USER_UNREAD_GRACE_MIN_COUNT=1):
            self.assertEqual(models.ReadFeedEntryUserMapping.objects.all().count(), 0)

            user = models.User.objects.create(email='test@test.com')

            feed = models.Feed.objects.create(
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

            feed_entry3 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 3 Title',
                url='http://example.com/entry3.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            feed_entry4 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 4 Title',
                url='http://example.com/entry4.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            models.FeedEntry.objects.bulk_create([feed_entry1, feed_entry2, feed_entry3, feed_entry4])

            feed_entry1.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-10)
            feed_entry1.save(update_fields=['published_at'])

            feed_entry2.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-20)
            feed_entry2.save(update_fields=['published_at'])

            archived_feed_entry_util.mark_archived_entries(archived_feed_entry_util.read_mapping_generator_fn(feed, user))

            self.assertEqual(models.ReadFeedEntryUserMapping.objects.all().count(), 2)

    def test_mark_archived_entries_equalmincount(self):
        with self.settings(USER_UNREAD_GRACE_INTERVAL=datetime.timedelta(days=-7), USER_UNREAD_GRACE_MIN_COUNT=2):
            self.assertEqual(models.ReadFeedEntryUserMapping.objects.all().count(), 0)

            user = models.User.objects.create(email='test@test.com')

            feed = models.Feed.objects.create(
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

            feed_entry3 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 3 Title',
                url='http://example.com/entry3.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            feed_entry4 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 4 Title',
                url='http://example.com/entry4.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            models.FeedEntry.objects.bulk_create([feed_entry1, feed_entry2, feed_entry3, feed_entry4])

            feed_entry1.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-10)
            feed_entry1.save(update_fields=['published_at'])

            feed_entry2.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-20)
            feed_entry2.save(update_fields=['published_at'])

            archived_feed_entry_util.mark_archived_entries(archived_feed_entry_util.read_mapping_generator_fn(feed, user))

            self.assertEqual(models.ReadFeedEntryUserMapping.objects.all().count(), 2)

    def test_mark_archived_entries_lessthanmincount(self):
        with self.settings(USER_UNREAD_GRACE_INTERVAL=datetime.timedelta(days=-7), USER_UNREAD_GRACE_MIN_COUNT=5):
            self.assertEqual(models.ReadFeedEntryUserMapping.objects.all().count(), 0)

            user = models.User.objects.create(email='test@test.com')

            feed = models.Feed.objects.create(
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

            feed_entry3 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 3 Title',
                url='http://example.com/entry3.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            feed_entry4 = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry 4 Title',
                url='http://example.com/entry4.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)

            models.FeedEntry.objects.bulk_create([feed_entry1, feed_entry2, feed_entry3, feed_entry4])

            feed_entry1.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-10)
            feed_entry1.save(update_fields=['published_at'])

            feed_entry2.published_at = user.created_at + settings.USER_UNREAD_GRACE_INTERVAL + datetime.timedelta(days=-1, minutes=-20)
            feed_entry2.save(update_fields=['published_at'])

            archived_feed_entry_util.mark_archived_entries(archived_feed_entry_util.read_mapping_generator_fn(feed, user))

            self.assertEqual(models.ReadFeedEntryUserMapping.objects.all().count(), 0)
