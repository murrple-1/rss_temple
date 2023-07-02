import datetime
import uuid
from typing import Callable

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.core.signals import setting_changed
from django.db.models.functions import Now
from django.db.models.query_utils import Q
from django.dispatch import receiver
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from api.models import AuthToken

_AUTH_TOKEN_EXPIRY_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _AUTH_TOKEN_EXPIRY_INTERVAL

    _AUTH_TOKEN_EXPIRY_INTERVAL = settings.AUTH_TOKEN_EXPIRY_INTERVAL


_load_global_settings()


class BearerAuthenticationMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if hasattr(request, "user") and request.user.is_authenticated:
            return self.get_response(request)

        request.user = self._user_from_request(request)  # type: ignore
        return self.get_response(request)

    def _user_from_request(
        self, request: HttpRequest
    ) -> AbstractBaseUser | AnonymousUser:
        if authorization := request.META.get("HTTP_AUTHORIZATION"):
            auth_token_uuid: uuid.UUID
            try:
                auth_token_uuid = AuthToken.extract_id_from_authorization_header(
                    authorization
                )
            except ValueError:
                return AnonymousUser()

            auth_token: AuthToken
            try:
                auth_token = AuthToken.objects.prefetch_related("user").get(
                    Q(uuid=auth_token_uuid)
                    & (Q(expires_at__isnull=True) | Q(expires_at__gt=Now()))
                )
            except AuthToken.DoesNotExist:
                return AnonymousUser()

            if auth_token.expires_at is not None:
                auth_token.expires_at = timezone.now() + _AUTH_TOKEN_EXPIRY_INTERVAL
                auth_token.save(update_fields=["expires_at"])

            return auth_token.user

        return AnonymousUser()
