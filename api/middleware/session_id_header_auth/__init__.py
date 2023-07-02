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

from api.models import APISession

_API_SESSION_EXPIRY_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _API_SESSION_EXPIRY_INTERVAL

    _API_SESSION_EXPIRY_INTERVAL = settings.API_SESSION_EXPIRY_INTERVAL


_load_global_settings()


class SessionIDHeaderAuthenticationMiddleware:
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
        if session_id := request.META.get("HTTP_X_SESSION_ID"):
            session_uuid: uuid.UUID
            try:
                session_uuid = uuid.UUID(session_id)
            except ValueError:
                return AnonymousUser()

            api_session: APISession
            try:
                api_session = APISession.objects.prefetch_related("user").get(
                    Q(uuid=session_uuid)
                    & (Q(expires_at__isnull=True) | Q(expires_at__gt=Now()))
                )
            except APISession.DoesNotExist:
                return AnonymousUser()

            if api_session.expires_at is not None:
                api_session.expires_at = timezone.now() + _API_SESSION_EXPIRY_INTERVAL
                api_session.save(update_fields=["expires_at"])

            return api_session.user

        return AnonymousUser()
