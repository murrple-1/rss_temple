from django.test import RequestFactory, SimpleTestCase
from silk.config import SilkyConfig

from rss_temple.silk_intercept import should_intercept


class SilkInterceptTestCase(SimpleTestCase):
    def setUp(self):
        super().setUp()

        self.old_intercept_percent = SilkyConfig().attrs["SILKY_INTERCEPT_PERCENT"]

    def tearDown(self):
        super().tearDown()

        SilkyConfig().attrs["SILKY_INTERCEPT_PERCENT"] = self.old_intercept_percent

    def test_should_intercept(self):
        SilkyConfig().attrs["SILKY_INTERCEPT_PERCENT"] = 100

        self.assertTrue(should_intercept(RequestFactory().get("/api/feed")))

        for path in (
            "/api/auth/login",
            "/api/auth/user",
            "/api/registration",
            "/api/registration/verifyemail",
            "/api/social/google",
        ):
            with self.subTest(path=path):
                self.assertFalse(should_intercept(RequestFactory().post(path)))

    def test_should_intercept_percent(self):
        SilkyConfig().attrs["SILKY_INTERCEPT_PERCENT"] = 0

        self.assertFalse(should_intercept(RequestFactory().get("/api/feed")))
