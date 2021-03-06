import datetime

from django.test import TestCase
from django.http.request import HttpRequest
from django.http.response import HttpResponse

from api.middleware import authentication
from api import models


class AuthenticationTestCase(TestCase):
    def test_succeed_authentication(self):
        with self.settings(
                REALM='Test Realm',
                AUTHENTICATION_DISABLE=[
                    (r'^/test/?$', ['POST'])
                ]):
            middleware = authentication.AuthenticationMiddleware(
                lambda request: HttpResponse())

            user = models.User.objects.create(email='test@test.com')

            session = models.Session.objects.create(
                user=user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))

            session_token = str(session.uuid)

            request = HttpRequest()
            request.path_info = '/test/'
            request.method = 'GET'
            request.META['HTTP_X_SESSION_TOKEN'] = session_token

            response = middleware(request)

            self.assertFalse('WWW-Authenticate' in response)
            self.assertEqual(response.status_code, 200)

    def test_failed_authentication(self):
        with self.settings(
                REALM='Test Realm',
                AUTHENTICATION_DISABLE=[
                    (r'^/test/?$', ['POST'])
                ]):
            middleware = authentication.AuthenticationMiddleware(
                lambda request: HttpResponse())

            request = HttpRequest()
            request.path_info = '/test/'
            request.method = 'GET'

            response = middleware(request)

            self.assertIn('WWW-Authenticate', response)
            self.assertEqual(response['WWW-Authenticate'],
                             'X-Basic realm="Test Realm"')
            self.assertEqual(response.status_code, 401)

    def test_no_authentication(self):
        with self.settings(
                REALM='Test Realm',
                AUTHENTICATION_DISABLE=[
                    (r'^/test/?$', ['POST'])
                ]):
            middleware = authentication.AuthenticationMiddleware(
                lambda request: HttpResponse())

            request = HttpRequest()
            request.path_info = '/test/'
            request.method = 'POST'

            response = middleware(request)

            self.assertFalse('WWW-Authenticate' in response)
            self.assertEqual(response.status_code, 200)

    def test_none_disable(self):
        with self.settings(
                REALM='Test Realm',
                AUTHENTICATION_DISABLE=None):
            middleware = authentication.AuthenticationMiddleware(
                lambda request: HttpResponse())

            request = HttpRequest()
            request.path_info = '/test/'
            request.method = 'GET'

            response = middleware(request)

            self.assertIn('WWW-Authenticate', response)
            self.assertEqual(response['WWW-Authenticate'],
                             'X-Basic realm="Test Realm"')
            self.assertEqual(response.status_code, 401)

    def test_none_realm(self):
        with self.settings(
                REALM=None,
                AUTHENTICATION_DISABLE=None):
            middleware = authentication.AuthenticationMiddleware(
                lambda request: HttpResponse())

            request = HttpRequest()
            request.path_info = '/test/'
            request.method = 'GET'

            response = middleware(request)

            self.assertIn('WWW-Authenticate', response)
            self.assertEqual(response['WWW-Authenticate'], 'X-Basic')
            self.assertEqual(response.status_code, 401)
