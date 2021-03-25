from django.test import TestCase

from api import content_sanitize


class ContentNormalizeTestCase(TestCase):
    def test_is_html(self):
        self.assertTrue(content_sanitize.is_html('<p>Some Text</p>'))
        self.assertTrue(content_sanitize.is_html('<p>Some Text'))
        self.assertTrue(content_sanitize.is_html('Some Text<br>Some More Text'))
        self.assertTrue(content_sanitize.is_html('Some Text<br/>Some More Text'))
        self.assertTrue(content_sanitize.is_html('Some Text<br />Some More Text'))

        self.assertFalse(content_sanitize.is_html('Some Text'))
        self.assertFalse(content_sanitize.is_html(''))

    def test_sanitize_html(self):
        self.assertEqual(content_sanitize.sanitize_html('<p>Some Text</p>'), '<p>Some Text</p>')
        self.assertEqual(content_sanitize.sanitize_html('<p>Some Text'), '<p>Some Text</p>')
        self.assertEqual(content_sanitize.sanitize_html('Some Text<br>Some More Text'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize_html('Some Text<br/>Some More Text'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize_html('Some Text<br />Some More Text'), 'Some Text<br>Some More Text')

        self.assertEqual(content_sanitize.sanitize_html('Some Text<br />Some More Text<script>console.log();</script>'), 'Some Text<br>Some More Text')

    def test_sanitize_text(self):
        self.assertEqual(content_sanitize.sanitize_plain('Some Text'), 'Some Text')
        self.assertEqual(content_sanitize.sanitize_plain('Some Text\nSome More Text'), 'Some Text<br>Some More Text')
        self.assertEqual(content_sanitize.sanitize_plain('1 > 2'), '1 &gt; 2')
        self.assertEqual(content_sanitize.sanitize_plain('Some Text\nSome More Text 1 < 2'), 'Some Text<br>Some More Text 1 &lt; 2')
