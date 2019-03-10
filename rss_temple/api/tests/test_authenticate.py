import datetime
import uuid

from django.test import TestCase
from django.http import HttpRequest

from api import authenticate, models


class AuthenticateTestCase(TestCase):
    def test_success(self):
        user = None
        try:
            user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User.objects.create(email='test@test.com')

        session = models.Session.objects.create(
            user=user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))

        session_token = str(session.uuid)

        request = HttpRequest()
        request.META['HTTP_X_SESSION_TOKEN'] = session_token

        self.assertTrue(authenticate.authenticate_http_request(request))

    def test_fail(self):
        request = HttpRequest()
        request.META['HTTP_X_SESSION_TOKEN'] = str(uuid.uuid4())

        self.assertFalse(authenticate.authenticate_http_request(request))

    def test_no_token(self):
        request = HttpRequest()

        self.assertFalse(authenticate.authenticate_http_request(request))

    def test_bad_session_token_format(self):
        request = HttpRequest()
        request.META['HTTP_X_SESSION_TOKEN'] = 'not a uuid'

        self.assertFalse(authenticate.authenticate_http_request(request))
