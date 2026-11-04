import base64
import datetime
import time
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.core.cache import caches
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework import exceptions

from api.authentication import (
    ExpiringTokenAuthentication,
    ThrottledVerifiedBasicAuthentication,
)
from api.models import Token, User


class ExpiringTokenAuthenticationTestCase(TestCase):
    def test_authenticate(self):
        authentication = ExpiringTokenAuthentication()

        user: User = User.objects.create_user("test@test.com", "password")
        expires_at = timezone.now() + datetime.timedelta(days=14)
        token = Token.objects.create(user=user, expires_at=expires_at)

        request = RequestFactory().get("/", HTTP_AUTHORIZATION=f"Token {token.key}")

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

        request = RequestFactory().get("/", HTTP_AUTHORIZATION=f"Token {token.key}")

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

        request = RequestFactory().get("/", HTTP_AUTHORIZATION=f"Token {token.key}")

        with self.assertRaises(exceptions.AuthenticationFailed):
            authentication.authenticate(request)

    def test_authenticate_badtoken(self):
        authentication = ExpiringTokenAuthentication()

        request = RequestFactory().get("/", HTTP_AUTHORIZATION="Token badtoken")

        with self.assertRaises(exceptions.AuthenticationFailed):
            authentication.authenticate(request)

    def test_authenticate_anonymoususer(self):
        authentication = ExpiringTokenAuthentication()

        request = RequestFactory().get("/")

        self.assertIsNone(authentication.authenticate(request))


@override_settings(
    BASIC_AUTH_MAX_FAILURES_PER_IP=5,
    BASIC_AUTH_MAX_FAILURES_PER_USER=3,
    BASIC_AUTH_FAILURE_WINDOW=datetime.timedelta(minutes=15),
)
class ThrottledVerifiedBasicAuthenticationTestCase(TestCase):
    def setUp(self):
        super().setUp()

        caches["throttle"].clear()

    @staticmethod
    def _create_user(email: str, verified: bool = True) -> User:
        user = User.objects.create_user(email, "password")
        EmailAddress.objects.create(
            user=user, email=email, primary=True, verified=verified
        )
        return user

    @staticmethod
    def _request(email: str, password: str, remote_addr: str = "203.0.113.1"):
        credentials = base64.b64encode(f"{email}:{password}".encode()).decode()
        return RequestFactory().get(
            "/",
            HTTP_AUTHORIZATION=f"Basic {credentials}",
            REMOTE_ADDR=remote_addr,
        )

    def test_authenticate(self):
        authentication = ThrottledVerifiedBasicAuthentication()

        user = self._create_user("test@test.com")

        auth_tuple = authentication.authenticate(
            self._request("test@test.com", "password")
        )
        assert auth_tuple is not None
        self.assertEqual(auth_tuple[0], user)

    def test_authenticate_unverified(self):
        authentication = ThrottledVerifiedBasicAuthentication()

        self._create_user("test@test.com", verified=False)

        with self.assertRaises(exceptions.AuthenticationFailed):
            authentication.authenticate(self._request("test@test.com", "password"))

    def test_authenticate_throttled_per_user(self):
        authentication = ThrottledVerifiedBasicAuthentication()

        self._create_user("test@test.com")

        # spread across IPs, so only the per-user limit applies
        for i in range(3):
            with self.assertRaises(exceptions.AuthenticationFailed):
                authentication.authenticate(
                    self._request("test@test.com", "badpassword", f"203.0.113.{i}")
                )

        # even the correct password is refused once the limit is hit
        with self.assertRaises(exceptions.Throttled):
            authentication.authenticate(
                self._request("TEST@test.com", "password", "203.0.113.100")
            )

    def test_authenticate_throttled_per_ip(self):
        authentication = ThrottledVerifiedBasicAuthentication()

        self._create_user("test@test.com")

        # spread across accounts, so only the per-IP limit applies
        for i in range(5):
            with self.assertRaises(exceptions.AuthenticationFailed):
                authentication.authenticate(
                    self._request(f"unknown{i}@test.com", "badpassword")
                )

        with self.assertRaises(exceptions.Throttled):
            authentication.authenticate(self._request("test@test.com", "password"))

        # other IPs are unaffected
        self.assertIsNotNone(
            authentication.authenticate(
                self._request("test@test.com", "password", "198.51.100.1")
            )
        )

    def test_authenticate_throttle_expires(self):
        authentication = ThrottledVerifiedBasicAuthentication()

        self._create_user("test@test.com")

        for _ in range(3):
            with self.assertRaises(exceptions.AuthenticationFailed):
                authentication.authenticate(
                    self._request("test@test.com", "badpassword")
                )

        with self.assertRaises(exceptions.Throttled):
            authentication.authenticate(self._request("test@test.com", "password"))

        later = time.time() + datetime.timedelta(minutes=16).total_seconds()
        with patch("django.core.cache.backends.locmem.time.time", return_value=later):
            self.assertIsNotNone(
                authentication.authenticate(self._request("test@test.com", "password"))
            )
