import datetime
from unittest.mock import Mock

from django.http.request import HttpRequest
from django.test import TestCase
from django.utils import timezone
from rest_framework import exceptions

from api.authentication import ExpiringTokenAuthentication
from api.models import Token, User


class ExpiringTokenAuthenticationTestCase(TestCase):
    def test_authenticate(self):
        authentication = ExpiringTokenAuthentication()

        user: User = User.objects.create_user("test@test.com", "password")
        expires_at = timezone.now() + datetime.timedelta(days=14)
        token = Token.objects.create(user=user, expires_at=expires_at)

        request = Mock(HttpRequest)
        request.META = {
            "HTTP_AUTHORIZATION": f"Token {token.key}",
        }

        tuple_ = authentication.authenticate(request)
        assert isinstance(tuple_, tuple)
        auth_user, auth_token = tuple_
        assert isinstance(auth_user, User)
        assert isinstance(auth_token, Token)
        self.assertEqual(auth_user.uuid, user.uuid)
        token.refresh_from_db()
        assert token.expires_at is not None
        self.assertGreater(token.expires_at, expires_at)

        token = Token.objects.create(user=user, expires_at=None)

        request = Mock(HttpRequest)
        request.META = {
            "HTTP_AUTHORIZATION": f"Token {token.key}",
        }

        tuple_ = authentication.authenticate(request)
        assert isinstance(tuple_, tuple)
        auth_user, auth_token = tuple_
        assert isinstance(auth_user, User)
        assert isinstance(auth_token, Token)
        self.assertEqual(auth_user.uuid, user.uuid)
        token.refresh_from_db()
        self.assertIsNone(token.expires_at)

    def test_authenticate_expired(self):
        authentication = ExpiringTokenAuthentication()

        user: User = User.objects.create_user("test@test.com", "password")
        expires_at = timezone.now() + datetime.timedelta(days=-1)
        token = Token.objects.create(user=user, expires_at=expires_at)

        request = Mock(HttpRequest)
        request.META = {
            "HTTP_AUTHORIZATION": f"Token {token.key}",
        }

        with self.assertRaises(exceptions.AuthenticationFailed):
            authentication.authenticate(request)

    def test_authenticate_badtoken(self):
        authentication = ExpiringTokenAuthentication()

        request = Mock(HttpRequest)
        request.META = {
            "HTTP_AUTHORIZATION": "Token badtoken",
        }

        with self.assertRaises(exceptions.AuthenticationFailed):
            authentication.authenticate(request)

    def test_authenticate_anonymoususer(self):
        authentication = ExpiringTokenAuthentication()

        request = Mock(HttpRequest)
        request.META = {}

        self.assertIsNone(authentication.authenticate(request))
