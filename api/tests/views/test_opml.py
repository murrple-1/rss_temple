import datetime
import logging

from django.core.management import call_command
from django.utils import timezone

from api import models
from api.tests.views import ViewTestCase


class OPMLTestCase(ViewTestCase):
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

    @staticmethod
    def _reset_db(fixture_path):
        call_command("flush", verbosity=0, interactive=False)
        call_command("loaddata", fixture_path, verbosity=0)

    @staticmethod
    def _login():
        user = models.User.objects.get(email="test@test.com")

        session = models.Session.objects.create(
            user=user,
            expires_at=timezone.now() + datetime.timedelta(days=2),
        )

        return str(session.uuid)

    def test_opml_get(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_mix-post.json")

        session_token_str = OPMLTestCase._login()

        response = self.client.get("/api/opml", HTTP_X_SESSION_TOKEN=session_token_str)
        self.assertEqual(response.status_code, 200, response.content)

    def test_opml_post(self):
        OPMLTestCase._reset_db("api/fixtures/default.json")

        session_token_str = OPMLTestCase._login()

        text = None
        with open("api/tests/test_files/opml/opml-mix.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 202, response.content)

    def test_opml_post_malformed_xml(self):
        OPMLTestCase._reset_db("api/fixtures/default.json")

        session_token_str = OPMLTestCase._login()

        text = None
        with open("api/tests/test_files/opml/invalid_xml.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_opml_post_malformed_opml(self):
        OPMLTestCase._reset_db("api/fixtures/default.json")

        session_token_str = OPMLTestCase._login()

        text = None
        with open("api/tests/test_files/opml/invalid_opml.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_opml_post_duplicates(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_mix-pre.json")

        session_token_str = OPMLTestCase._login()

        text = None
        with open("api/tests/test_files/opml/opml-mix.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 202, response.content)

    def test_opml_post_duplicatesinopml(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_duplicates-pre.json")

        session_token_str = OPMLTestCase._login()

        text = None
        with open("api/tests/test_files/opml/opml-duplicates.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 202, response.content)

    def test_opml_post_done_before(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_no_404-post.json")

        session_token_str = OPMLTestCase._login()

        text = None
        with open("api/tests/test_files/opml/opml-no-404.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_opml_post_quick_subscribe(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_no_404-post.json")

        user = models.User.objects.get(email="test@test.com")

        models.SubscribedFeedUserMapping.objects.filter(user=user).first().delete()

        session_token_str = OPMLTestCase._login()

        text = None
        with open("api/tests/test_files/opml/opml-no-404.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
            HTTP_X_SESSION_TOKEN=session_token_str,
        )
        self.assertEqual(response.status_code, 204, response.content)
