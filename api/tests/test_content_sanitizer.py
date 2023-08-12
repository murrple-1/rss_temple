from django.test import TestCase

from api import content_sanitize


class ContentSanitizerTestCase(TestCase):
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
                '<a href="https://test.com/entry" target="_blank">Link</a>',
            ),
            (
                '<a href="https://test.com/entry" target="_self">Link</a>',
                '<a href="https://test.com/entry" target="_blank">Link</a>',
            ),
            (
                '<a href="https://test.com/entry"><a href="https://test.com/entry"></a></a>',
                "",
            ),
            (
                '<a href="https://test.com/entry"><a href="https://test.com/entry">Link</a></a>',
                '<a href="https://test.com/entry" target="_blank">Link</a>',
            ),
            ("<p>Ben &amp; Jerry's</p>", "<p>Ben &amp; Jerry's</p>"),
            ("<p>Ben & Jerry's</p>", "<p>Ben &amp; Jerry's</p>"),
            ("<iframe></iframe>", ""),
            ('<iframe src="https://slashdot.org/post1.html"></iframe>', ""),
            (
                '<iframe src="https://slashdot.org/post1.html"><p>Inner Text</p></iframe>',
                "",
            ),
            ('<iframe src="http://::12.34.56.78]/"><p>Inner Text</p></iframe>', ""),
            ("Some Text", "Some Text"),
            ("Some Text\nSome More Text", "Some Text<br>Some More Text"),
            ("1 > 2", "1 &gt; 2"),
            ("Some Text\nSome More Text 1 < 2", "Some Text<br>Some More Text 1 &lt; 2"),
            (
                "Teenage winger Salma Paralluelo scores a 111th-minute winner as Spain beat the Netherlands to reach the semi-finals of the Women&#x27;s World Cup for the first time.",
                "Teenage winger Salma Paralluelo scores a 111th-minute winner as Spain beat the Netherlands to reach the semi-finals of the Women's World Cup for the first time.",
            ),
        ]:
            with self.subTest(input=input_, expected_output=expected_output):
                self.assertEqual(content_sanitize.sanitize(input_), expected_output)
