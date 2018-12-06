import logging
import datetime

from django.test import TestCase, Client

import ujson

from api import models

# TODO finish tests
class FeedEntryTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

        try:
            cls.user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            cls.user = models.User(email='test@test.com')
            cls.user.save()

        session = models.Session(
            user=cls.user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))
        session.save()

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

    def test_feedentry_get(self):
        feed = None
        try:
            feed = models.Feed.objects.get(
                feed_url='http://example.com/rss.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://example.com/rss.xml',
                title='Sample Feed',
                home_url='http://example.com',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed.save()

        feed_entry = models.FeedEntry.objects.filter(feed=feed).first()
        if feed_entry is None:
            feed_entry = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry Title',
                url='http://example.com/entry1.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)
            feed_entry.hash = hash(feed_entry)
            feed_entry.save()

        c = Client()

        response = c.get('/api/feedentry/{}'.format(str(feed_entry.uuid)),
            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_feedentries_get(self):
        feed = None
        try:
            feed = models.Feed.objects.get(
                feed_url='http://example.com/rss.xml')
        except models.Feed.DoesNotExist:
            feed = models.Feed(
                feed_url='http://example.com/rss.xml',
                title='Sample Feed',
                home_url='http://example.com',
                published_at=datetime.datetime.utcnow(),
                updated_at=None,
                db_updated_at=None)
            feed.save()

        feed_entry = models.FeedEntry.objects.filter(feed=feed).first()
        if feed_entry is None:
            feed_entry = models.FeedEntry(
                id=None,
                feed=feed,
                created_at=None,
                updated_at=None,
                title='Feed Entry Title',
                url='http://example.com/entry1.html',
                content='Some Entry content',
                author_name='John Doe',
                db_updated_at=None)
            feed_entry.hash = hash(feed_entry)
            feed_entry.save()

        c = Client()

        response = c.get('/api/feedentries',
            HTTP_X_SESSION_TOKEN=FeedEntryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)
