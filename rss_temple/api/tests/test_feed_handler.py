from unittest import TestCase
import os
import time
from multiprocessing import Process
from http.server import HTTPServer, SimpleHTTPRequestHandler

from api import feed_handler
from api.exceptions import QueryException

def _http_server():
    os.chdir('api/tests/test_files/')

    with HTTPServer(('', 8080), SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()

class FeedHandlerTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http_process = Process(target=_http_server)
        cls.http_process.start()

        time.sleep(2.0)

    @classmethod
    def tearDownClass(cls):
        cls.http_process.terminate()

        time.sleep(2.0)

    def test_url_2_d(self):
        feed_handler.url_2_d('http://localhost:8080/well_formed.xml')

    def test_request_fail(self):
        with self.assertRaises(QueryException):
            feed_handler.url_2_d('http://localhost:8080/sample-404.xml')

    def test_well_formed(self):
        text = None
        with open('api/tests/test_files/well_formed.xml', 'r') as f:
            text = f.read()

        feed_handler.text_2_d(text)
