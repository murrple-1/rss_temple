import logging

from django.test import TestCase

from api import feed_handler, models
from api.exceptions import QueryException


class FeedHandlerTestCase(TestCase):
    FEED_TYPES = [
        'atom_0.3',
        'atom_1.0',
        'rss_1.0',
        'rss_2.0',
        'rss_2.0_ns',
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_logger_level = logging.getLogger('rss_temple').getEffectiveLevel()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger('rss_temple').setLevel(cls.old_logger_level)

    def test_well_formed(self):
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            text = None
            with open(f'api/tests/test_files/{feed_type}/well_formed.xml', 'r') as f:
                text = f.read()

            feed_handler.text_2_d(text)

    def test_malformed(self):
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            text = None
            with open(f'api/tests/test_files/{feed_type}/malformed.xml', 'r') as f:
                text = f.read()

            with self.assertRaises(QueryException):
                feed_handler.text_2_d(text)

    def test_d_feed_2_feed(self):
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            text = None
            with open(f'api/tests/test_files/{feed_type}/well_formed.xml', 'r') as f:
                text = f.read()

            d = feed_handler.text_2_d(text)

            url = 'http://www.example.com'

            feed = feed_handler.d_feed_2_feed(d.feed, url)

            self.assertEqual(feed.feed_url, url)
            self.assertEqual(feed.title, d.feed.get('title'))
            self.assertEqual(feed.home_url, d.feed.get('link'))

    def test_d_feed_2_feed_entry(self):
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            text = None
            with open(f'api/tests/test_files/{feed_type}/well_formed.xml', 'r') as f:
                text = f.read()

            d = feed_handler.text_2_d(text)

            feed_entry = feed_handler.d_entry_2_feed_entry(d.entries[0])
            self.assertIsInstance(feed_entry, models.FeedEntry)

    def test_d_feed_2_feed_tags(self):
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            text = None
            with open(f'api/tests/test_files/{feed_type}/well_formed.xml', 'r') as f:
                text = f.read()

            d = feed_handler.text_2_d(text)

            feed_tags = feed_handler.d_feed_2_feed_tags(d.feed)
            self.assertIs(type(feed_tags), frozenset)

            self.assertGreater(len(feed_tags), 0, f'{feed_type} is empty')

            for feed_tag in feed_tags:
                self.assertIs(type(feed_tag), str)

    def test_d_entry_2_entry_tags(self):
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            text = None
            with open(f'api/tests/test_files/{feed_type}/well_formed.xml', 'r') as f:
                text = f.read()

            d = feed_handler.text_2_d(text)

            entry_tags = feed_handler.d_entry_2_entry_tags(d.entries[0])
            self.assertIs(type(entry_tags), frozenset)

            self.assertGreater(len(entry_tags), 0, f'{feed_type} is empty')

            for entry_tag in entry_tags:
                self.assertIs(type(entry_tag), str)

    def test_d_feed_2_feed_entry_plaintext(self):
        text = None
        with open('api/tests/test_files/atom_1.0/well_formed_text.xml', 'r') as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        feed_entry = feed_handler.d_entry_2_feed_entry(d.entries[0])
        self.assertIsInstance(feed_entry, models.FeedEntry)
