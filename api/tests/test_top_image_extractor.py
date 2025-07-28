import logging
from typing import ClassVar

from django.test import tag

from api.tests import TestFileServerTestCase
from api.tests.utils import generate_top_image_pages
from api.top_image_extractor import (
    TryAgain,
    extract_top_image_src,
    find_top_image_src_candidates,
)


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

    @tag("slow")
    def test_find_top_image_src_candidates_meta_og_image(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/meta_og_image.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertCountEqual(
            result,
            [f"{TopImageExtractorTestCase.live_server_url}/site/images/256x256.jpg"],
        )

    @tag("slow")
    def test_find_top_image_src_candidates_bad_meta_og_image(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/bad_meta_og_image.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)

    @tag("slow")
    def test_find_top_image_src_candidates_meta_twitter_image(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/meta_twitter_image.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertCountEqual(
            result,
            [f"{TopImageExtractorTestCase.live_server_url}/site/images/256x256.jpg"],
        )

    @tag("slow")
    def test_find_top_image_src_candidates_bad_meta_twitter_image(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/bad_meta_twitter_image.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)

    @tag("slow")
    def test_find_top_image_src_candidates_multiple_img_tags(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/multiple_img_tags.html",
            -1,
            max_image_frequency=5,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertCountEqual(
            result,
            [
                f"{TopImageExtractorTestCase.live_server_url}/site/images/256x256.jpg",
                f"{TopImageExtractorTestCase.live_server_url}/site/images/512x512.jpg",
            ],
        )

    @tag("slow")
    def test_find_top_image_src_candidates_decorative_and_bad_images(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/decorative_and_bad_images.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertCountEqual(
            result,
            [f"{TopImageExtractorTestCase.live_server_url}/site/images/256x256.jpg"],
        )

    @tag("slow")
    def test_find_top_image_src_candidates_response_too_big(self):
        with self.assertRaises(TryAgain):
            find_top_image_src_candidates(
                f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/response_too_big.html",
                100,
            )

    @tag("slow")
    def test_find_top_image_src_candidates_image_too_small(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/image_too_small.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)

    @tag("slow")
    def test_find_top_image_src_candidates_img_with_bad_aspect_ratio(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/img_with_bad_aspect_ratio.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)

    @tag("slow")
    def test_find_top_image_src_candidates_img_without_src(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/img_without_src.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)

    @tag("slow")
    def test_find_top_image_src_candidates_bad_image_formats(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/bad_image_formats.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)

    @tag("slow")
    def test_find_top_image_src_candidates_bad_classes(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/bad_classes.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)

    @tag("slow")
    def test_find_top_image_src_candidates_bad_ids(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/bad_ids.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)

    @tag("slow")
    def test_find_top_image_src_candidates_bad_alt_texts(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/bad_alt_texts.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertCountEqual(
            result,
            [
                f"{TopImageExtractorTestCase.live_server_url}/site/images/512x512.jpg",
            ],
        )

    @tag("slow")
    def test_find_top_image_src_candidates_bad_img_srcs(self):
        result = find_top_image_src_candidates(
            f"{TopImageExtractorTestCase.live_server_url}/site/top_image_extractor/bad_img_srcs.html",
            -1,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)
