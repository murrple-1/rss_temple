import base64
import datetime
import uuid

from django.conf import settings

import api.models as models
from api.exceptions import QueryException

def authenticate_http_request(request):
    user = _user_from_http_request__session_token(request)
    if not user:
        return False

    request.user = user

    return True


_SESSION_EXPIRY_INTERVAL = settings.SESSION_EXPIRY_INTERVAL


def _user_from_http_request__session_token(request):
    if 'HTTP_X_SESSION_TOKEN' in request.META:
        session_token = request.META['HTTP_X_SESSION_TOKEN']
        session_token_uuid = None
        try:
            session_token_uuid = uuid.UUID(session_token)
        except ValueError:
            return None

        try:
            session = models.Session.objects.prefetch_related('user').get(uuid=session_token_uuid)
            if session.expires_at is None or session.expires_at > datetime.datetime.utcnow():
                session.expires_at = (
                    datetime.datetime.utcnow() +
                    _SESSION_EXPIRY_INTERVAL)
                session.save(update_fields=['expires_at'])

                return session.user
        except models.Session.DoesNotExist:
            pass
    return None
