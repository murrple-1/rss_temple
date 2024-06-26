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
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/single_rss_xml.html",
                1,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/single_atom_xml.html",
                1,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/multi.html",
                6,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/relative.html",
                2,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/base_absolute.html",
                2,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/base_relative.html",
                2,
            ),
            (
                f"{ExtractExposedFeedsTestCase.live_server_url}/site/exposed_feeds/bad_base_relative.html",
                0,
            ),
        ]:
            with self.subTest(url=url):
                exposed_feeds = extract_exposed_feeds(url, -1)
                self.assertEqual(len(exposed_feeds), expected_feed_count)

    @tag("slow")
    def test_extract_exposed_feeds_justafeed(self):
        exposed_feeds = extract_exposed_feeds(
            f"{ExtractExposedFeedsTestCase.live_server_url}/rss_2.0/well_formed.xml", -1
        )
        self.assertEqual(len(exposed_feeds), 1)

    @tag("slow")
    def test_extract_exposed_feeds_notfound(self):
        exposed_feeds = extract_exposed_feeds(
            f"{ExtractExposedFeedsTestCase.live_server_url}/not_found.html", -1
        )
        self.assertEqual(len(exposed_feeds), 0)

    @tag("slow")
    def test_extract_exposed_feeds_nothtml(self):
        exposed_feeds = extract_exposed_feeds(
            f"{ExtractExposedFeedsTestCase.live_server_url}/site/images/128x128.jpg", -1
        )
        self.assertEqual(len(exposed_feeds), 0)

    @tag("slow")
    def test_extract_exposed_feeds_noversion(self):
        exposed_feeds = extract_exposed_feeds(
            f"{ExtractExposedFeedsTestCase.live_server_url}/no_version/actually_html.xml",
            -1,
        )
        self.assertEqual(len(exposed_feeds), 0)

        exposed_feeds = extract_exposed_feeds(
            f"{ExtractExposedFeedsTestCase.live_server_url}/no_version/actually_xhtml.xml",
            -1,
        )
        self.assertEqual(len(exposed_feeds), 0)
