import datetime
import uuid

from django.conf import settings
from django.core.signals import setting_changed
from django.db.models.functions import Now
from django.db.models.query_utils import Q
from django.dispatch import receiver

from api import models

_SESSION_EXPIRY_INTERVAL = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _SESSION_EXPIRY_INTERVAL

    _SESSION_EXPIRY_INTERVAL = settings.SESSION_EXPIRY_INTERVAL


_load_global_settings()


def authenticate_http_request(request):
    user = _user_from_http_request__session_token(request)

    if not user:
        return False

    request.user = user

    return True


def _user_from_http_request__session_token(request):
    if "HTTP_X_SESSION_TOKEN" in request.META:
        session_token = request.META["HTTP_X_SESSION_TOKEN"]
        session_token_uuid = None
        try:
            session_token_uuid = uuid.UUID(session_token)
        except ValueError:
            return None

        session = None
        try:
            session = models.Session.objects.prefetch_related("user").get(
                Q(uuid=session_token_uuid)
                & (Q(expires_at__isnull=True) | Q(expires_at__gt=Now()))
            )
        except models.Session.DoesNotExist:
            return None

        if session:
            if session.expires_at is not None:
                session.expires_at = (
                    datetime.datetime.now(datetime.timezone.utc)
                    + _SESSION_EXPIRY_INTERVAL
                )
                session.save(update_fields=["expires_at"])

            return session.user

    return None
