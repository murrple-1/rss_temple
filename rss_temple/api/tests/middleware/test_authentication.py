import importlib
import datetime

from django.test import TestCase
from django.http.request import HttpRequest
from django.http.response import HttpResponse

import api.middleware.authentication as authentication
from api import models

class AuthenticationTestCase(TestCase):
    def test_succeed_authentication(self):
        with self.settings(
            REALM='Test Realm',
            AUTHENTICATION_DISABLE=[
                (r'^/test/?$', ['POST'])
            ]):
            importlib.reload(authentication)
            middleware = authentication.AuthenticationMiddleware(lambda request: HttpResponse())

            user = None
            try:
                user = models.User.objects.get(email='test@test.com')
            except models.User.DoesNotExist:
                user = models.User()
                user.email = 'test@test.com'

                user.save()

            session = models.Session()
            session.user = user
            session.expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=2))

            session.save()

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
            importlib.reload(authentication)
            middleware = authentication.AuthenticationMiddleware(lambda request: HttpResponse())

            request = HttpRequest()
            request.path_info = '/test/'
            request.method = 'GET'

            response = middleware(request)

            self.assertTrue('WWW-Authenticate' in response)
            self.assertEqual(response['WWW-Authenticate'], 'X-Basic realm="Test Realm"')
            self.assertEqual(response.status_code, 401)

    def test_no_authentication(self):
        with self.settings(
            REALM='Test Realm',
            AUTHENTICATION_DISABLE=[
                (r'^/test/?$', ['POST'])
            ]):
            importlib.reload(authentication)
            middleware = authentication.AuthenticationMiddleware(lambda request: HttpResponse())

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
            importlib.reload(authentication)
            middleware = authentication.AuthenticationMiddleware(lambda request: HttpResponse())

            request = HttpRequest()
            request.path_info = '/test/'
            request.method = 'GET'

            response = middleware(request)

            self.assertTrue('WWW-Authenticate' in response)
            self.assertEqual(response['WWW-Authenticate'], 'X-Basic realm="Test Realm"')
            self.assertEqual(response.status_code, 401)

    def test_none_realm(self):
        with self.settings(
            REALM=None,
            AUTHENTICATION_DISABLE=None):
            importlib.reload(authentication)
            middleware = authentication.AuthenticationMiddleware(lambda request: HttpResponse())

            request = HttpRequest()
            request.path_info = '/test/'
            request.method = 'GET'

            response = middleware(request)

            self.assertTrue('WWW-Authenticate' in response)
            self.assertEqual(response['WWW-Authenticate'], 'X-Basic')
            self.assertEqual(response.status_code, 401)
