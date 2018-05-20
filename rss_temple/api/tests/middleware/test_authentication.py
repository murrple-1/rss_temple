from django.test import TestCase
from django.http.request import HttpRequest
from django.http.response import HttpResponse

import api.middleware.authentication as authentication

class AuthenticationTestCase(TestCase):
    # TODO
    def test_middleware(self):
        middleware = authentication.AuthenticationMiddleware(lambda request: HttpResponse())

        request = HttpRequest()

        response = middleware(request)
