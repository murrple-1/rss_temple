import importlib

from django.test import TestCase
from django.http.request import HttpRequest
from django.http.response import HttpResponse

import api.middleware.cors as cors

class CORSTestCase(TestCase):
    def test_middleware(self):
        with self.settings(CORS_ALLOW_ORIGINS='*',
            CORS_ALLOW_METHODS='GET,POST,OPTIONS',
            CORS_ALLOW_HEADERS='Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization',
            CORS_EXPOSE_HEADERS=''):
            importlib.reload(cors)
            middleware = cors.CORSMiddleware(lambda request: HttpResponse())

            request = HttpRequest()

            response = middleware(request)
