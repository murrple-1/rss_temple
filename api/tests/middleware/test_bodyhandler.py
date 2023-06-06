from django.http.response import HttpResponse
from django.test import TestCase

from api.middleware import bodyhandler


class BodyHandlerTestCase(TestCase):
    def test_middleware(self):
        middleware = bodyhandler.BodyHandlerMiddleware(lambda request: HttpResponse())

        class MockHttpRequest:
            def __init__(self):
                self.body = None

        request = MockHttpRequest()

        response = middleware(request)
        self.assertIsNotNone(response)
