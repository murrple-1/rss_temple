import logging
from typing import ClassVar

from django.test import tag

from api.exposed_feed_extractor import extract_exposed_feeds
from api.tests import TestFileServerTestCase


class ExtractExposedFeedsTestCase(TestFileServerTestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)
        logging.getLogger("django").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    @tag("slow")
    def test_extract_exposed_feeds(self):
        for url, expected_feed_count in [
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/single.html",
                1,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/multi.html",
                3,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/relative.html",
                1,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/base_absolute.html",
                1,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/base_relative.html",
                1,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/bad_base_relative.html",
                0,
            ),
        ]:
            with self.subTest(url=url):
                exposed_feeds = extract_exposed_feeds(url)
                self.assertEqual(len(exposed_feeds), expected_feed_count)

    @tag("slow")
    def test_extract_exposed_feeds_justafeed(self):
        exposed_feeds = extract_exposed_feeds(
            f"{ExtractExposedFeedsTestCase.live_server_url}/rss_2.0/well_formed.xml"
        )
        self.assertEqual(len(exposed_feeds), 1)

    @tag("slow")
    def test_extract_exposed_feeds_notfound(self):
        exposed_feeds = extract_exposed_feeds(
            f"{ExtractExposedFeedsTestCase.live_server_url}/not_found.html"
        )
        self.assertEqual(len(exposed_feeds), 0)
