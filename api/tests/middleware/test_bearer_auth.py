import datetime
import uuid
from typing import ClassVar
from unittest.mock import Mock

from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.test import TestCase
from django.utils import timezone

from api.middleware import bearer_auth
from api.models import AuthToken, User


class MiddlewareTestCase(TestCase):
    middleware: ClassVar[bearer_auth.BearerAuthenticationMiddleware]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.middleware = bearer_auth.BearerAuthenticationMiddleware(
            lambda request: HttpResponse()
        )

    def test_succeed(self):
        user = User.objects.create_user("test@test.com", "password")

        auth_token = AuthToken.objects.create(
            user=user,
            expires_at=timezone.now() + datetime.timedelta(days=2),
        )

        token_str = str(auth_token.uuid)

        request = Mock(HttpRequest)

        request.META = {"HTTP_AUTHORIZATION": f"Bearer {token_str}"}

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
        request.META = {"HTTP_AUTHORIZATION": "Bearer bad_id"}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertFalse(request.user.is_authenticated)

    def test_missing_id(self):
        request = Mock(HttpRequest)
        request.META = {"HTTP_AUTHORIZATION": f"Bearer {uuid.UUID(int=0)}"}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertFalse(request.user.is_authenticated)

    def test_old_id(self):
        user = User.objects.create_user("test@test.com", "password")

        auth_token = AuthToken.objects.create(
            user=user,
            expires_at=timezone.now() + datetime.timedelta(days=-1),
        )

        token_str = str(auth_token.uuid)

        request = Mock(HttpRequest)

        request.META = {"HTTP_AUTHORIZATION": f"Bearer {token_str}"}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertFalse(request.user.is_authenticated)

    def test_never_expire(self):
        user = User.objects.create_user("test@test.com", "password")

        auth_token = AuthToken.objects.create(
            user=user,
            expires_at=None,
        )

        token_str = str(auth_token.uuid)

        request = Mock(HttpRequest)

        request.META = {"HTTP_AUTHORIZATION": f"Bearer {token_str}"}

        self.middleware(request)

        self.assertTrue(hasattr(request, "user"))
        self.assertTrue(request.user.is_authenticated)
