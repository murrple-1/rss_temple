from django.test import TestCase

from api import content_sanitize


class ContentSanitizerTestCase(TestCase):
    def test_is_html(self):
        self.assertTrue(content_sanitize.is_html('<p>Some Text</p>'))
        self.assertTrue(content_sanitize.is_html('<p>Some Text'))
        self.assertTrue(content_sanitize.is_html(
            'Some Text<br>Some More Text'))
        self.assertTrue(content_sanitize.is_html(
            'Some Text<br/>Some More Text'))
        self.assertTrue(content_sanitize.is_html(
            'Some Text<br />Some More Text'))

        self.assertFalse(content_sanitize.is_html('Some Text'))
        self.assertFalse(content_sanitize.is_html(''))

    def test_sanitize_html(self):
        self.assertEqual(content_sanitize.sanitize_html(
            '<p>Some Text</p>'), '<p>Some Text</p>')
        self.assertEqual(content_sanitize.sanitize_html(
            '<p>Some Text'), '<p>Some Text</p>')
        self.assertEqual(content_sanitize.sanitize_html(
            'Some Text<br>Some More Text'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize_html(
            'Some Text<br/>Some More Text'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize_html(
            'Some Text<br />Some More Text'), 'Some Text<br>Some More Text')

        self.assertEqual(content_sanitize.sanitize_html(
            'Some Text<br />Some More Text<script>console.log();</script>'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize_html(
            'Some Text<br />Some More Text<script><script>console.log();</script></script>'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize_html(
            'Some Text<br />Some More Text<style>>html {font-size: 50px;}</style>'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize_html(
            'Some Text<br />Some More Text<style><style>html {font-size: 50px;}</style></style>'), 'Some Text<br>Some More Text')

        self.assertEqual(content_sanitize.sanitize_html(
            '<img src="https://test.com/something.png">'), '<img src="https://test.com/something.png">')
        self.assertEqual(content_sanitize.sanitize_html(
            '<img src="http://test.com/something.png">'), '')
        self.assertEqual(content_sanitize.sanitize_html(
            '<img src="smb://192.168.0.1/something.png">'), '')

        self.assertEqual(content_sanitize.sanitize_html(
            '<a href="https://test.com/entry"></a>'), '')
        self.assertEqual(content_sanitize.sanitize_html(
            '<a href="https://test.com/entry">Link</a>'), '<a href="https://test.com/entry">Link</a>')
        self.assertEqual(content_sanitize.sanitize_html(
            '<a href="https://test.com/entry"><a href="https://test.com/entry"></a></a>'), '')
        self.assertEqual(content_sanitize.sanitize_html(
            '<a href="https://test.com/entry"><a href="https://test.com/entry">Link</a></a>'), '<a href="https://test.com/entry">Link</a>')

        self.assertEqual(content_sanitize.sanitize_html(
            '<iframe></iframe>'), '')
        self.assertEqual(content_sanitize.sanitize_html(
            '<iframe src="https://slashdot.org/post1.html"></iframe>'), '')
        self.assertEqual(content_sanitize.sanitize_html(
            '<iframe src="https://slashdot.org/post1.html"><p>Inner Text</p></iframe>'), '')
        self.assertEqual(content_sanitize.sanitize_html(
            '<iframe src="http://::12.34.56.78]/"><p>Inner Text</p></iframe>'), '')

    def test_sanitize_text(self):
        self.assertEqual(content_sanitize.sanitize_plain(
            'Some Text'), 'Some Text')
        self.assertEqual(content_sanitize.sanitize_plain(
            'Some Text\nSome More Text'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize_plain('1 > 2'), '1 &gt; 2')
        self.assertEqual(content_sanitize.sanitize_plain(
            'Some Text\nSome More Text 1 < 2'), 'Some Text<br>Some More Text 1 &lt; 2')
        self.assertEqual(content_sanitize.sanitize_plain(
            '<p>Some Text</p>'), '&lt;p&gt;Some Text&lt;/p&gt;')

    def test_sanitize(self):
        self.assertEqual(content_sanitize.sanitize(
            '<p>Some Text</p>'), '<p>Some Text</p>')
        self.assertEqual(content_sanitize.sanitize(
            '<p>Some Text'), '<p>Some Text</p>')
        self.assertEqual(content_sanitize.sanitize(
            'Some Text<br>Some More Text'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize(
            'Some Text<br/>Some More Text'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize(
            'Some Text<br />Some More Text'), 'Some Text<br>Some More Text')

        self.assertEqual(content_sanitize.sanitize(
            'Some Text<br />Some More Text<script>console.log();</script>'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize(
            'Some Text<br />Some More Text<script><script>console.log();</script></script>'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize(
            'Some Text<br />Some More Text<style>>html {font-size: 50px;}</style>'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize(
            'Some Text<br />Some More Text<style><style>html {font-size: 50px;}</style></style>'), 'Some Text<br>Some More Text')

        self.assertEqual(content_sanitize.sanitize(
            '<img src="https://test.com/something.png">'), '<img src="https://test.com/something.png">')
        self.assertEqual(content_sanitize.sanitize(
            '<img src="http://test.com/something.png">'), '')
        self.assertEqual(content_sanitize.sanitize(
            '<img src="smb://192.168.0.1/something.png">'), '')

        self.assertEqual(content_sanitize.sanitize(
            '<a href="https://test.com/entry"></a>'), '')
        self.assertEqual(content_sanitize.sanitize(
            '<a href="https://test.com/entry">Link</a>'), '<a href="https://test.com/entry">Link</a>')
        self.assertEqual(content_sanitize.sanitize(
            '<a href="https://test.com/entry"><a href="https://test.com/entry"></a></a>'), '')
        self.assertEqual(content_sanitize.sanitize(
            '<a href="https://test.com/entry"><a href="https://test.com/entry">Link</a></a>'), '<a href="https://test.com/entry">Link</a>')

        self.assertEqual(content_sanitize.sanitize('Some Text'), 'Some Text')
        self.assertEqual(content_sanitize.sanitize(
            'Some Text\nSome More Text'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize('1 > 2'), '1 &gt; 2')
        self.assertEqual(content_sanitize.sanitize(
            'Some Text\nSome More Text 1 < 2'), 'Some Text<br>Some More Text 1 &lt; 2')

        self.assertEqual(content_sanitize.sanitize(
            '<iframe></iframe>'), '')
        self.assertEqual(content_sanitize.sanitize(
            '<iframe src="https://slashdot.org/post1.html"></iframe>'), '')
        self.assertEqual(content_sanitize.sanitize(
            '<iframe src="https://slashdot.org/post1.html"><p>Inner Text</p></iframe>'), '')
        self.assertEqual(content_sanitize.sanitize(
            '<iframe src="http://::12.34.56.78]/"><p>Inner Text</p></iframe>'), '')
