import logging
from typing import ClassVar

from django.test import tag

from api.tests import TestFileServerTestCase
from api.tests.utils import generate_top_image_pages
from api.top_image_extractor import extract_top_image_src


class TopImageExtractorTestCase(TestFileServerTestCase):
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
    def test_extract_top_image_src(self):
        srcs: list[str | None] = []
        for t in generate_top_image_pages(TopImageExtractorTestCase.live_server_url):
            srcs.append(extract_top_image_src(t.url, -1, 2000, 256, 256))

        self.assertTrue(any(src is None for src in srcs))
        self.assertTrue(any(src is not None for src in srcs))

    @tag("slow")
    def test_extract_top_image_src_notfound(self):
        self.assertIsNone(
            extract_top_image_src(
                f"{TopImageExtractorTestCase.live_server_url}/site/entry_notexist.html",
                -1,
                2000,
                256,
                256,
            )
        )

    @tag("slow")
    def test_extract_top_image_src_nothtml(self):
        self.assertIsNone(
            extract_top_image_src(
                f"{TopImageExtractorTestCase.live_server_url}/site/images/128x128.jpg",
                -1,
                2000,
                256,
                256,
            )
        )
