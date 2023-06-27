import datetime
import uuid
from typing import ClassVar
from unittest.mock import Mock

from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.test import TestCase
from django.utils import timezone

from api.middleware import session_id_header_auth
from api.models import APISession, User


class AuthenticationTestCase(TestCase):
    middleware: ClassVar[session_id_header_auth.SessionIDHeaderAuthenticationMiddleware]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.middleware = session_id_header_auth.SessionIDHeaderAuthenticationMiddleware(
            lambda request: HttpResponse()
        )

    def test_succeed(self):
        user = User.objects.create_user("test@test.com", "password")

        api_session = APISession.objects.create(
            user=user,
            expires_at=timezone.now() + datetime.timedelta(days=2),
        )

        session_token = str(api_session.uuid)

        request = Mock(HttpRequest)

        request.META = {"HTTP_X_SESSION_ID": session_token}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertTrue(request.user.is_authenticated)

    def test_no_id(self):
        request = Mock(HttpRequest)
        request.META = {}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertFalse(request.user.is_authenticated)

    def test_malformed_id(self):
        request = Mock(HttpRequest)
        request.META = {"HTTP_X_SESSION_ID": "bad_id"}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertFalse(request.user.is_authenticated)

    def test_missing_id(self):
        request = Mock(HttpRequest)
        request.META = {"HTTP_X_SESSION_ID": str(uuid.UUID(int=0))}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertFalse(request.user.is_authenticated)

    def test_old_id(self):
        user = User.objects.create_user("test@test.com", "password")

        api_session = APISession.objects.create(
            user=user,
            expires_at=timezone.now() + datetime.timedelta(days=-1),
        )

        session_token = str(api_session.uuid)

        request = Mock(HttpRequest)

        request.META = {"HTTP_X_SESSION_ID": session_token}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertFalse(request.user.is_authenticated)

    def test_never_expire(self):
        user = User.objects.create_user("test@test.com", "password")

        api_session = APISession.objects.create(
            user=user,
            expires_at=None,
        )

        session_token = str(api_session.uuid)

        request = Mock(HttpRequest)

        request.META = {"HTTP_X_SESSION_ID": session_token}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertTrue(request.user.is_authenticated)
