from unittest import TestCase
import logging
import time
from multiprocessing import Process

from api import feed_handler
from api.exceptions import QueryException

def _http_server_process():
    import os
    import sys
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    sys.stdout = open('/dev/null', 'w')
    sys.stderr = sys.stdout

    os.chdir('api/tests/test_files/')

    with HTTPServer(('', 8080), SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()

class FeedHandlerTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

        cls.http_process = Process(target=_http_server_process)
        cls.http_process.start()

        time.sleep(2.0)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

        cls.http_process.terminate()

        time.sleep(2.0)

    def test_url_2_d(self):
        feed_handler.url_2_d('http://localhost:8080/rss/well_formed.xml')

    def test_request_fail(self):
        with self.assertRaises(QueryException):
            feed_handler.url_2_d('http://localhost:8080/rss/sample-404.xml')

    def test_well_formed_rss(self):
        text = None
        with open('api/tests/test_files/rss/well_formed.xml', 'r') as f:
            text = f.read()

        feed_handler.text_2_d(text)

    def test_well_formed_atom(self):
        text = None
        with open('api/tests/test_files/atom/well_formed.xml', 'r') as f:
            text = f.read()

        feed_handler.text_2_d(text)

    def test_malformed_rss(self):
        text = None
        with open('api/tests/test_files/rss/malformed.xml', 'r') as f:
            text = f.read()

        with self.assertRaises(QueryException):
            feed_handler.text_2_d(text)

    def test_malformed_atom(self):
        text = None
        with open('api/tests/test_files/atom/malformed.xml', 'r') as f:
            text = f.read()

        with self.assertRaises(QueryException):
            feed_handler.text_2_d(text)

    def test_d_feed_2_feed_rss(self):
        text = None
        with open('api/tests/test_files/rss/well_formed.xml', 'r') as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        url = 'http://www.example.com'

        feed = feed_handler.d_feed_2_feed(d.feed, url)

        self.assertEqual(feed.feed_url, url)
        self.assertEqual(feed.title, d.feed.get('title'))
        self.assertEqual(feed.home_url, d.feed.get('link'))

    def test_d_feed_2_feed_atom(self):
        text = None
        with open('api/tests/test_files/atom/well_formed.xml', 'r') as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        url = 'http://www.example.com'

        feed = feed_handler.d_feed_2_feed(d.feed, url)

        self.assertEqual(feed.feed_url, url)
        self.assertEqual(feed.title, d.feed.get('title'))
        self.assertEqual(feed.home_url, d.feed.get('link'))

    def test_d_feed_2_feed_entry_rss(self):
        text = None
        with open('api/tests/test_files/rss/well_formed.xml', 'r') as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        feed_entry = feed_handler.d_entry_2_feed_entry(d.entries[0])

    def test_d_feed_2_feed_entry_atom(self):
        text = None
        with open('api/tests/test_files/atom/well_formed.xml', 'r') as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        feed_entry = feed_handler.d_entry_2_feed_entry(d.entries[0])

    def test_d_feed_2_feed_tags_rss(self):
        text = None
        with open('api/tests/test_files/rss/well_formed.xml', 'r') as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        feed_tags = feed_handler.d_feed_2_feed_tags(d.feed)

    def test_d_feed_2_feed_tags_atom(self):
        text = None
        with open('api/tests/test_files/atom/well_formed.xml', 'r') as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        feed_tags = feed_handler.d_feed_2_feed_tags(d.feed)

    def test_d_entry_2_entry_tags_rss(self):
        text = None
        with open('api/tests/test_files/rss/well_formed.xml', 'r') as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        entry_tags = feed_handler.d_entry_2_entry_tags(d.entries[0])

    def test_d_entry_2_entry_tags_atom(self):
        text = None
        with open('api/tests/test_files/atom/well_formed.xml', 'r') as f:
            text = f.read()

        d = feed_handler.text_2_d(text)

        entry_tags = feed_handler.d_entry_2_entry_tags(d.entries[0])
