from django.test import TestCase
from django.http.response import HttpResponse

import api.middleware.bodyhandler as bodyhandler

class BodyHandlerTestCase(TestCase):
    def test_middleware(self):
        middleware = bodyhandler.BodyHandlerMiddleware(lambda request: HttpResponse())

        class MockHttpRequest:
            def __init__(self):
                self.body = None

        request = MockHttpRequest()

        response = middleware(request)