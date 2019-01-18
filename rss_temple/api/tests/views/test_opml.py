import logging
import datetime

from django.test import TestCase, Client
from django.core.management import call_command

from api import models


class OPMLTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

    @staticmethod
    def _reset_db(fixture_path):
        call_command('flush', verbosity=0, interactive=False)
        call_command('loaddata', fixture_path, verbosity=0)

    @staticmethod
    def _login():
        user = models.User.objects.get(email='test@test.com')

        session = models.Session.objects.create(
            user=user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))

        return str(session.uuid)

    def test_opml_get(self):
        OPMLTestCase._reset_db('api/tests/fixtures/opml_mix-post.json')

        session_token_str = OPMLTestCase._login()

        c = Client()

        response = c.get('/api/opml',
                         HTTP_X_SESSION_TOKEN=session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_opml_post(self):
        OPMLTestCase._reset_db('api/fixtures/default.json')

        session_token_str = OPMLTestCase._login()

        c = Client()

        text = None
        with open('api/tests/test_files/opml/opml-mix.xml', 'r') as f:
            text = f.read()

        response = c.post('/api/opml', text,
                          content_type='text/xml', HTTP_X_SESSION_TOKEN=session_token_str)
        self.assertEqual(response.status_code, 202)

    def test_opml_post_malformed_xml(self):
        OPMLTestCase._reset_db('api/fixtures/default.json')

        session_token_str = OPMLTestCase._login()

        c = Client()

        text = None
        with open('api/tests/test_files/opml/invalid_xml.xml', 'r') as f:
            text = f.read()

        response = c.post('/api/opml', text,
                          content_type='text/xml', HTTP_X_SESSION_TOKEN=session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_opml_post_malformed_opml(self):
        OPMLTestCase._reset_db('api/fixtures/default.json')

        session_token_str = OPMLTestCase._login()

        c = Client()

        text = None
        with open('api/tests/test_files/opml/invalid_opml.xml', 'r') as f:
            text = f.read()

        response = c.post('/api/opml', text,
                          content_type='text/xml', HTTP_X_SESSION_TOKEN=session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_opml_post_duplicates(self):
        OPMLTestCase._reset_db('api/tests/fixtures/opml_mix-pre.json')

        session_token_str = OPMLTestCase._login()

        c = Client()

        text = None
        with open('api/tests/test_files/opml/opml-mix.xml', 'r') as f:
            text = f.read()

        response = c.post('/api/opml', text,
                          content_type='text/xml', HTTP_X_SESSION_TOKEN=session_token_str)
        self.assertEqual(response.status_code, 202)

    def test_opml_post_done_before(self):
        OPMLTestCase._reset_db('api/tests/fixtures/opml_no_404-post.json')

        session_token_str = OPMLTestCase._login()

        c = Client()

        text = None
        with open('api/tests/test_files/opml/opml-no-404.xml', 'r') as f:
            text = f.read()

        response = c.post('/api/opml', text,
                          content_type='text/xml', HTTP_X_SESSION_TOKEN=session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_opml_post_quick_subscribe(self):
        OPMLTestCase._reset_db('api/tests/fixtures/opml_no_404-post.json')

        user = models.User.objects.get(email='test@test.com')

        models.SubscribedFeedUserMapping.objects.filter(
            user=user).first().delete()

        session_token_str = OPMLTestCase._login()

        c = Client()

        text = None
        with open('api/tests/test_files/opml/opml-no-404.xml', 'r') as f:
            text = f.read()

        response = c.post('/api/opml', text,
                          content_type='text/xml', HTTP_X_SESSION_TOKEN=session_token_str)
        self.assertEqual(response.status_code, 200)
