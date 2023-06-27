from unittest.mock import Mock

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.test import TestCase

from api import decorators
from api.models import User


class RequiresAuthenticatedUserTestCase(TestCase):
    def test_success(self):
        @decorators.requires_authenticated_user()
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse()

        request = Mock(HttpRequest)
        request.user = User()

        response = view(request)
        self.assertEqual(response.status_code, 200, response.content)

    def test_fail_realm(self):
        with self.settings(REALM="TEST REALM"):

            @decorators.requires_authenticated_user()
            def view(request: HttpRequest) -> HttpResponse:
                return HttpResponse()

            request = Mock(HttpRequest)
            request.user = AnonymousUser()

            response = view(request)
            self.assertEqual(response.status_code, 401, response.content)
            self.assertIn("WWW-Authenticate", response.headers)
            self.assertIn('realm="TEST REALM"', response.headers["WWW-Authenticate"])

    def test_fail_no_realm(self):
        with self.settings(REALM=None):

            @decorators.requires_authenticated_user()
            def view(request: HttpRequest) -> HttpResponse:
                return HttpResponse()

            request = Mock(HttpRequest)
            request.user = AnonymousUser()

            response = view(request)
            self.assertEqual(response.status_code, 401, response.content)
            self.assertIn("WWW-Authenticate", response.headers)
            self.assertNotIn('realm="TEST REALM"', response.headers["WWW-Authenticate"])
