from django.test import TestCase

from api import content_type_util


class ContentTypeUtilTestCase(TestCase):
    def test_is_html(self):
        self.assertFalse(content_type_util.is_html("image/png"))

        for input_ in ["text/html", "application/xhtml+xml"]:
            with self.subTest(input=input_):
                self.assertTrue(content_type_util.is_html(input_))

    def test_is_feed(self):
        self.assertFalse(content_type_util.is_feed("image/png"))

        for input_ in [
            "application/xml",
            "application/rss+xml",
            "application/rdf+xml",
            "application/atom+xml",
            "application/json",
            "text/xml",
            "xml/rss",
        ]:
            with self.subTest(input=input_):
                self.assertTrue(content_type_util.is_feed(input_))

        # common mislabels
        for input_ in ["text/html", "application/octet-stream"]:
            with self.subTest(input=input_):
                self.assertTrue(content_type_util.is_feed(input_))

    def test_is_image(self):
        self.assertFalse(content_type_util.is_image("text/html"))

        # from https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types#image_types
        for input_ in [
            "image/apng",
            "image/avif",
            "image/gif",
            "image/jpeg",
            "image/png",
            "image/svg+xml",
            "image/webp",
        ]:
            with self.subTest(input=input_):
                self.assertTrue(content_type_util.is_image(input_))
