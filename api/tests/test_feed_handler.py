import datetime
import logging
from typing import ClassVar

from django.test import TestCase

from api import feed_handler
from api.models import FeedEntry


class FeedHandlerTestCase(TestCase):
    old_logger_level: ClassVar[int]
    now: ClassVar[datetime.datetime]

    FEED_TYPES = [
        "atom_0.3",
        "atom_1.0",
        "rss_1.0",
        "rss_2.0",
        "rss_2.0_ns",
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)

        cls.now = datetime.datetime(2020, 1, 1, 0, 0, 0, 0, datetime.timezone.utc)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_logger_level)

    def test_well_formed(self):
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            text: str
            with open(f"api/tests/test_files/{feed_type}/well_formed.xml", "r") as f:
                text = f.read()

            feed_handler.text_2_d(text)

    def test_malformed(self):
        text: str
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            with open(f"api/tests/test_files/{feed_type}/malformed.xml", "r") as f:
                text = f.read()

            with self.assertRaises(feed_handler.FeedHandlerError):
                feed_handler.text_2_d(text)

        with open("api/tests/test_files/no_version/actually_xhtml.xml", "r") as f:
            text = f.read()

        with self.assertRaisesRegex(
            feed_handler.FeedHandlerError, r"^not a recognized feed version$"
        ):
            feed_handler.text_2_d(text)

        with open("api/tests/test_files/no_version/actually_html.xml", "r") as f:
            text = f.read()

        with self.assertRaisesRegex(feed_handler.FeedHandlerError, r"^$"):
            feed_handler.text_2_d(text)

    def test_d_feed_2_feed(self):
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            text: str
            with open(f"api/tests/test_files/{feed_type}/well_formed.xml", "r") as f:
                text = f.read()

            d = feed_handler.text_2_d(text)

            url = "http://www.example.com"

            feed = feed_handler.d_feed_2_feed(d.feed, url, FeedHandlerTestCase.now)

            self.assertEqual(feed.feed_url, url)
            self.assertEqual(feed.title, d.feed.get("title"))
            self.assertEqual(feed.home_url, d.feed.get("link"))

    def test_d_feed_2_feed_entry(self):
        for feed_type in FeedHandlerTestCase.FEED_TYPES:
            text: str
            with open(f"api/tests/test_files/{feed_type}/well_formed.xml", "r") as f:
                text = f.read()

            d = feed_handler.text_2_d(text)

            feed_entry = feed_handler.d_entry_2_feed_entry(
                d.entries[0], FeedHandlerTestCase.now
            )
            self.assertIsInstance(feed_entry, FeedEntry)

    def test_d_feed_2_feed_entry_plaintext(self):
        text: str
        with open("api/tests/test_files/atom_1.0/well_formed_text.xml", "r") as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        feed_entry = feed_handler.d_entry_2_feed_entry(
            d.entries[0], FeedHandlerTestCase.now
        )
        self.assertIsInstance(feed_entry, FeedEntry)

    def test_d_feed_2_feed_entry_no_title(self):
        text: str
        with open("api/tests/test_files/atom_1.0/well_formed_no_title.xml", "r") as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        with self.assertRaises(ValueError):
            feed_handler.d_entry_2_feed_entry(d.entries[0], FeedHandlerTestCase.now)

    def test_d_feed_2_feed_entry_no_url(self):
        text: str
        with open("api/tests/test_files/atom_1.0/well_formed_no_url.xml", "r") as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        with self.assertRaises(ValueError):
            feed_handler.d_entry_2_feed_entry(d.entries[0], FeedHandlerTestCase.now)

    def test_d_feed_2_feed_entry_url_is_id(self):
        text: str
        with open("api/tests/test_files/atom_1.0/well_formed_url_is_id.xml", "r") as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        with self.assertRaises(ValueError):
            feed_handler.d_entry_2_feed_entry(d.entries[0], FeedHandlerTestCase.now)

    def test_d_feed_2_feed_entry_no_content(self):
        text: str
        with open("api/tests/test_files/atom_1.0/well_formed_no_content.xml", "r") as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        with self.assertRaises(ValueError):
            feed_handler.d_entry_2_feed_entry(d.entries[0], FeedHandlerTestCase.now)

    def test_d_feed_2_feed_entry_enclosure(self):
        text: str
        with open("api/tests/test_files/rss_2.0/well_formed.xml", "r") as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        feed_entry = feed_handler.d_entry_2_feed_entry(
            d.entries[1], FeedHandlerTestCase.now
        )
        self.assertIsInstance(feed_entry, FeedEntry)
