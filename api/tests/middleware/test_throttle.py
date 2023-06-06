import datetime

from django.http.response import HttpResponse
from django.test import TestCase

from api.middleware import throttle


class ThrottleTestCase(TestCase):
    def test_middleware(self):
        middleware = throttle.ThrottleMiddleware(lambda request: HttpResponse())

        class MockHttpRequest:
            def __init__(self):
                self.META = {
                    "REMOTE_ADDR": "192.168.0.1",
                }
                self.path_info = "/"
                self.method = "GET"

        request = MockHttpRequest()

        with self.settings(THROTTLE_ENABLE=[("test", [], 30, 60)]):
            response = middleware(request)
            self.assertIsNotNone(response)

    def test_enable_none(self):
        middleware = throttle.ThrottleMiddleware(lambda request: HttpResponse())

        class MockHttpRequest:
            def __init__(self):
                self.META = {
                    "REMOTE_ADDR": "192.168.0.1",
                }
                self.path_info = "/"
                self.method = "GET"

        request = MockHttpRequest()

        with self.settings(THROTTLE_ENABLE=None):
            response = middleware(request)
            self.assertIsNotNone(response)

    def test_interval_types(self):
        middleware = throttle.ThrottleMiddleware(lambda request: HttpResponse())

        class MockHttpRequest:
            def __init__(self):
                self.META = {
                    "REMOTE_ADDR": "192.168.0.1",
                }
                self.path_info = "/"
                self.method = "GET"

        request = MockHttpRequest()

        with self.settings(THROTTLE_ENABLE=[("test", [], 30, 60)]):
            response = middleware(request)
            self.assertIsNotNone(response)

        with self.settings(
            THROTTLE_ENABLE=[("test", [], 30, datetime.timedelta(seconds=60))]
        ):
            response = middleware(request)
            self.assertIsNotNone(response)

    def test_no_ip(self):
        middleware = throttle.ThrottleMiddleware(lambda request: HttpResponse())

        class MockHttpRequest:
            def __init__(self):
                self.META = {}
                self.path_info = "/"
                self.method = "GET"

        request = MockHttpRequest()

        with self.settings(THROTTLE_ENABLE=[("test", [], 30, 60)]):
            response = middleware(request)
            self.assertEqual(response.status_code, 400, response.content)

    def test_throttling(self):
        middleware = throttle.ThrottleMiddleware(lambda request: HttpResponse())

        class MockHttpRequest:
            def __init__(self):
                self.META = {
                    "REMOTE_ADDR": "192.168.0.1",
                }
                self.path_info = "/"
                self.method = "GET"

        request = MockHttpRequest()

        with self.settings(
            THROTTLE_ENABLE=[("test", [(r"^/$", "GET")], 1, 60)],
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "default-cache",
                },
                "throttle": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "throttle-cache",
                },
            },
        ):
            response = middleware(request)
            self.assertEqual(response.status_code, 200, response.content)

            response = middleware(request)
            self.assertEqual(response.status_code, 429, response.content)
