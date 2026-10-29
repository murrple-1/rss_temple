import logging
from typing import ClassVar

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import Feed, SubscribedFeedUserMapping, User, UserCategory
from api.tests.utils import disable_silk, disable_throttling


@disable_silk()
@disable_throttling()
class OPMLTestCase(APITestCase):
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

    @staticmethod
    def _reset_db(fixture_path):
        call_command("flush", verbosity=0, interactive=False)
        call_command("loaddata", fixture_path, verbosity=0)

    def _login(self):
        user = User.objects.get(email="test@test.com")

        self.client.force_authenticate(user=user)

    def test_OPMLView_get(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_mix-post.json")

        self._login()

        response = self.client.get("/api/opml")
        self.assertEqual(response.status_code, 200, response.content)

    def test_OPMLView_get_ignores_other_users_categories(self):
        user = User.objects.create_user("test@test.com", None)
        other_user = User.objects.create_user("other@test.com", None)

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )
        SubscribedFeedUserMapping.objects.create(feed=feed, user=user)

        other_user_category = UserCategory.objects.create(
            user=other_user, text="Other User Category"
        )
        other_user_category.feeds.add(feed)

        self._login()

        response = self.client.get("/api/opml")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn(b"Other User Category", response.content)

    def test_OPMLView_post(self):
        OPMLTestCase._reset_db("api/fixtures/default.json")

        self._login()
        text: str
        with open("api/tests/test_files/opml/opml-mix.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
        )
        self.assertEqual(response.status_code, 202, response.content)

    def test_OPMLView_post_malformed_xml(self):
        OPMLTestCase._reset_db("api/fixtures/default.json")

        self._login()

        text: str
        with open("api/tests/test_files/opml/invalid_xml.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_OPMLView_post_malformed_opml(self):
        OPMLTestCase._reset_db("api/fixtures/default.json")

        self._login()

        text: str
        with open("api/tests/test_files/opml/invalid_opml.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_OPMLView_post_duplicates(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_mix-pre.json")

        self._login()

        text: str
        with open("api/tests/test_files/opml/opml-mix.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
        )
        self.assertEqual(response.status_code, 202, response.content)

    def test_OPMLView_post_duplicatesinopml(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_duplicates-pre.json")

        self._login()

        text: str
        with open("api/tests/test_files/opml/opml-duplicates.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
        )
        self.assertEqual(response.status_code, 202, response.content)

    def test_OPMLView_post_done_before(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_no_404-post.json")

        self._login()

        text: str
        with open("api/tests/test_files/opml/opml-no-404.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
        )
        self.assertEqual(response.status_code, 204, response.content)

    def test_OPMLView_post_quick_subscribe(self):
        OPMLTestCase._reset_db("api/tests/fixtures/opml_no_404-post.json")

        user = User.objects.get(email="test@test.com")

        subscribed_feed_user_mapping = SubscribedFeedUserMapping.objects.filter(
            user=user
        ).first()
        assert subscribed_feed_user_mapping is not None
        subscribed_feed_user_mapping.delete()

        self._login()

        text: str
        with open("api/tests/test_files/opml/opml-no-404.xml", "r") as f:
            text = f.read()

        response = self.client.post(
            "/api/opml",
            text,
            content_type="text/xml",
        )
        self.assertEqual(response.status_code, 204, response.content)
