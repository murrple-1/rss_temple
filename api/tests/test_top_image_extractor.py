import logging
from typing import ClassVar
import io
from unittest.mock import MagicMock, patch

from django.test import tag
from PIL import Image

from api.requests_extensions import ResponseTooBig
from api.tests import TestFileServerTestCase
from api.tests.utils import generate_top_image_pages
from api.top_image_extractor import extract_top_image_src
from api import rss_requests
from api import top_image_extractor as tie


def _make_image_response(width=300, height=300, fmt="JPEG", byte_count=5000):
    content: bytes
    with io.BytesIO() as img_bytes:
        img = Image.new("RGB", (width, height), color="red")
        img.save(img_bytes, format=fmt)
        img_bytes.seek(0)
        content = img_bytes.read()

    if byte_count > len(content):
        content += b"\0" * (byte_count - len(content))

    mock_resp = MagicMock()
    mock_resp.headers = {
        "Content-Type": "image/jpeg",
        "Content-Length": str(len(content)),
    }
    mock_resp.status_code = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    mock_resp.iter_content = lambda chunk_size: [content]
    mock_resp.raw = io.BytesIO(content)
    return mock_resp, content


def _make_html_response(html: str, content_type="text/html", status_code=200):
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": content_type}
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    mock_resp.text = html
    mock_resp.content = html.encode("utf-8")
    return mock_resp


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

    # TODO experimental below

    def test_meta_og_image(self):
        html = """
        <html>
          <head>
            <meta property="og:image" content="http://img.com/img1.jpg"/>
            <title>Example Page</title>
          </head>
          <body>
            <img src="img2.jpg"/>
          </body>
        </html>
        """
        html_resp = _make_html_response(html)
        img1_resp, img1_bytes = _make_image_response()
        img2_resp, img2_bytes = _make_image_response()

        def fake_get(url, **kwargs):
            if url.endswith("img1.jpg"):
                return img1_resp
            elif url.endswith("img2.jpg"):
                return img2_resp
            else:
                return html_resp

        def fake_safe_response_content(response, *args):
            if response is img1_resp:
                return img1_bytes
            elif response is img2_resp:
                return img2_bytes
            raise RuntimeError("unknown response")

        with (
            patch.object(rss_requests, "get", side_effect=fake_get),
            patch.object(
                tie, "safe_response_content", side_effect=fake_safe_response_content
            ),
            patch.object(tie, "safe_response_text", return_value=html),
        ):
            result = tie.find_top_image_src_candidates("http://test.com", -1)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(
            frozenset(result), {"http://img.com/img1.jpg", "http://test.com/img2.jpg"}
        )
        self.assertEqual(result[0], "http://img.com/img1.jpg")

    def test_meta_twitter_image(self):
        html = """
        <html>
          <head>
            <meta name="twitter:image" content="http://img.com/imgtw.jpg"/>
          </head>
          <body></body>
        </html>
        """
        html_resp = _make_html_response(html)
        img_resp, img_bytes = _make_image_response()

        def fake_get(url, **kwargs):
            if url.endswith("imgtw.jpg"):
                return img_resp
            else:
                return html_resp

        with (
            patch.object(rss_requests, "get", side_effect=fake_get),
            patch.object(tie, "safe_response_content", return_value=img_bytes),
            patch.object(tie, "safe_response_text", return_value=html),
        ):
            result = tie.find_top_image_src_candidates("http://test.com", -1)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(frozenset(result), {"http://img.com/imgtw.jpg"})

    def test_img_tag_selection(self):
        html = """
        <html>
          <body>
            <img src="img1.jpg"/>
            <img src="img2.jpg"/>
          </body>
        </html>
        """
        html_resp = _make_html_response(html)
        img1_resp, img1_bytes = _make_image_response(width=400, height=300)
        img2_resp, img2_bytes = _make_image_response(width=500, height=400)

        def fake_get(url, **kwargs):
            if url.endswith("img1.jpg"):
                return img1_resp
            elif url.endswith("img2.jpg"):
                return img2_resp
            else:
                return html_resp

        def fake_safe_response_content(response, *args):
            if response is img1_resp:
                return img1_bytes
            elif response is img2_resp:
                return img2_bytes
            raise RuntimeError("unknown response")

        with (
            patch.object(rss_requests, "get", side_effect=fake_get),
            patch.object(
                tie, "safe_response_content", side_effect=fake_safe_response_content
            ),
            patch.object(tie, "safe_response_text", return_value=html),
        ):
            result = tie.find_top_image_src_candidates("http://test.com", -1)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(
            frozenset(result), {"http://test.com/img1.jpg", "http://test.com/img2.jpg"}
        )

    def test_decorative_and_bad_images(self):
        html = """
        <html>
          <body>
            <img src="ad_banner.jpg"/>
            <img src="logo_icon.png"/>
            <img src="main_image.jpg"/>
          </body>
        </html>
        """
        html_resp = _make_html_response(html)
        img_resp, img_bytes = _make_image_response()

        def fake_get(url, **kwargs):
            if url.endswith("main_image.jpg"):
                return img_resp
            else:
                return html_resp

        with (
            patch.object(rss_requests, "get", side_effect=fake_get),
            patch.object(tie, "safe_response_content", return_value=img_bytes),
            patch.object(tie, "safe_response_text", return_value=html),
        ):
            result = tie.find_top_image_src_candidates("http://test.com", -1)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(frozenset(result), {"http://test.com/main_image.jpg"})

    def test_response_too_big(self):
        html = """
        <html>
          <body>
            <img src="img.jpg"/>
          </body>
        </html>
        """
        html_resp = _make_html_response(html)
        img_resp, _ = _make_image_response()

        def fake_get(url, **kwargs):
            if url.endswith("img.jpg"):
                return img_resp
            else:
                return html_resp

        def fake_safe_response_content__raise_too_big(*args, **kwargs):
            raise ResponseTooBig()

        with (
            patch.object(rss_requests, "get", side_effect=fake_get),
            patch.object(
                tie,
                "safe_response_content",
                side_effect=fake_safe_response_content__raise_too_big,
            ),
            patch.object(tie, "safe_response_text", return_value=html),
        ):
            with self.assertRaises(tie.TryAgain):
                tie.find_top_image_src_candidates("http://test.com", 3000)

    def test_image_too_small(self):
        html = """
        <html>
          <body>
            <img src="imgsmall.jpg"/>
          </body>
        </html>
        """
        html_resp = _make_html_response(html)
        img_resp, img_bytes = _make_image_response(width=10, height=10, byte_count=100)

        def fake_get(url, **kwargs):
            if url.endswith("imgsmall.jpg"):
                return img_resp
            else:
                return html_resp

        with (
            patch.object(rss_requests, "get", side_effect=fake_get),
            patch.object(tie, "safe_response_content", return_value=img_bytes),
            patch.object(tie, "safe_response_text", return_value=html),
        ):
            result = tie.find_top_image_src_candidates("http://test.com", -1)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)

    def test_img_with_aspect_ratio(self):
        html = """
        <html>
          <body>
            <img src="panorama.jpg"/>
          </body>
        </html>
        """
        html_resp = _make_html_response(html)
        img_resp, img_bytes = _make_image_response(width=2000, height=200)

        def fake_get(url, **kwargs):
            if url.endswith("panorama.jpg"):
                return img_resp
            else:
                return html_resp

        with (
            patch.object(rss_requests, "get", side_effect=fake_get),
            patch.object(tie, "safe_response_content", return_value=img_bytes),
            patch.object(tie, "safe_response_text", return_value=html),
        ):
            result = tie.find_top_image_src_candidates("http://test.com", -1)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 0)
