from django.test import TestCase

from api import content_sanitize


class ContentSanitizerTestCase(TestCase):
    def test_is_html(self):
        for text in [
            "<p>Some Text</p>",
            "<p>Some Text",
            "Some Text<br>Some More Text",
            "Some Text<br/>Some More Text",
            "Some Text<br />Some More Text",
        ]:
            with self.subTest(text=text):
                self.assertTrue(content_sanitize.is_html(text))

        for text in ["Some Text", ""]:
            with self.subTest(text=text):
                self.assertFalse(content_sanitize.is_html(text))

    def test_sanitize_html(self):
        for input_, expected_output in [
            ("<p>Some Text</p>", "<p>Some Text</p>"),
            ("<p>Some Text", "<p>Some Text</p>"),
            ("Some Text<br>Some More Text", "Some Text<br>Some More Text"),
            ("Some Text<br/>Some More Text", "Some Text<br>Some More Text"),
            ("Some Text<br />Some More Text", "Some Text<br>Some More Text"),
            (
                "Some Text<br />Some More Text<script>console.log();</script>",
                "Some Text<br>Some More Text",
            ),
            (
                "Some Text<br />Some More Text<script><script>console.log();</script></script>",
                "Some Text<br>Some More Text",
            ),
            (
                "Some Text<br />Some More Text<style>>html {font-size: 50px;}</style>",
                "Some Text<br>Some More Text",
            ),
            (
                "Some Text<br />Some More Text<style><style>html {font-size: 50px;}</style></style>",
                "Some Text<br>Some More Text",
            ),
            (
                '<img src="https://test.com/something.png">',
                '<img src="https://test.com/something.png">',
            ),
            ('<img src="http://test.com/something.png">', ""),
            ('<img src="smb://192.168.0.1/something.png">', ""),
            ('<a href="https://test.com/entry"></a>', ""),
            (
                '<a href="https://test.com/entry">Link</a>',
                '<a href="https://test.com/entry">Link</a>',
            ),
            (
                '<a href="https://test.com/entry"><a href="https://test.com/entry"></a></a>',
                "",
            ),
            (
                '<a href="https://test.com/entry"><a href="https://test.com/entry">Link</a></a>',
                '<a href="https://test.com/entry">Link</a>',
            ),
            ("<iframe></iframe>", ""),
            ('<iframe src="https://slashdot.org/post1.html"></iframe>', ""),
            (
                '<iframe src="https://slashdot.org/post1.html"><p>Inner Text</p></iframe>',
                "",
            ),
            ('<iframe src="http://::12.34.56.78]/"><p>Inner Text</p></iframe>', ""),
        ]:
            with self.subTest(input=input_, expected_output=expected_output):
                self.assertEqual(
                    content_sanitize.sanitize_html(input_), expected_output
                )

    def test_sanitize_text(self):
        for input_, expected_output in [
            ("Some Text", "Some Text"),
            ("Some Text\nSome More Text", "Some Text<br>Some More Text"),
            ("1 > 2", "1 &gt; 2"),
            ("Some Text\nSome More Text 1 < 2", "Some Text<br>Some More Text 1 &lt; 2"),
            ("<p>Some Text</p>", "&lt;p&gt;Some Text&lt;/p&gt;"),
        ]:
            with self.subTest(input=input_, expected_output=expected_output):
                self.assertEqual(
                    content_sanitize.sanitize_plain(input_), expected_output
                )

    def test_sanitize(self):
        for input_, expected_output in [
            ("<p>Some Text</p>", "<p>Some Text</p>"),
            ("<p>Some Text", "<p>Some Text</p>"),
            ("Some Text<br>Some More Text", "Some Text<br>Some More Text"),
            ("Some Text<br/>Some More Text", "Some Text<br>Some More Text"),
            ("Some Text<br />Some More Text", "Some Text<br>Some More Text"),
            (
                "Some Text<br />Some More Text<script>console.log();</script>",
                "Some Text<br>Some More Text",
            ),
            (
                "Some Text<br />Some More Text<script><script>console.log();</script></script>",
                "Some Text<br>Some More Text",
            ),
            (
                "Some Text<br />Some More Text<style>>html {font-size: 50px;}</style>",
                "Some Text<br>Some More Text",
            ),
            (
                "Some Text<br />Some More Text<style><style>html {font-size: 50px;}</style></style>",
                "Some Text<br>Some More Text",
            ),
            (
                '<img src="https://test.com/something.png">',
                '<img src="https://test.com/something.png">',
            ),
            ('<img src="http://test.com/something.png">', ""),
            ('<img src="smb://192.168.0.1/something.png">', ""),
            ('<a href="https://test.com/entry"></a>', ""),
            (
                '<a href="https://test.com/entry">Link</a>',
                '<a href="https://test.com/entry">Link</a>',
            ),
            (
                '<a href="https://test.com/entry"><a href="https://test.com/entry"></a></a>',
                "",
            ),
            (
                '<a href="https://test.com/entry"><a href="https://test.com/entry">Link</a></a>',
                '<a href="https://test.com/entry">Link</a>',
            ),
            ("Some Text", "Some Text"),
            ("Some Text\nSome More Text", "Some Text<br>Some More Text"),
            ("1 > 2", "1 &gt; 2"),
            ("Some Text\nSome More Text 1 < 2", "Some Text<br>Some More Text 1 &lt; 2"),
            ("<iframe></iframe>", ""),
            ('<iframe src="https://slashdot.org/post1.html"></iframe>', ""),
            (
                '<iframe src="https://slashdot.org/post1.html"><p>Inner Text</p></iframe>',
                "",
            ),
            ('<iframe src="http://::12.34.56.78]/"><p>Inner Text</p></iframe>', ""),
        ]:
            with self.subTest(input=input_, expected_output=expected_output):
                self.assertEqual(content_sanitize.sanitize(input_), expected_output)
