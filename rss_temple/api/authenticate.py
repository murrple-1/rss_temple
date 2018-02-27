import base64
import datetime
import uuid

from django.conf import settings

import argon2

import api.models as models
from api.exceptions import QueryException

def authenticate_http_request(request):
    user = _user_from_http_request__credentials(
        request) or _user_from_http_request__session_token(request)
    if not user:
        return False

    request.user = user

    return True

__password_hasher = argon2.PasswordHasher()
def _user_from_http_request__credentials(request):
    if 'HTTP_AUTHORIZATION' in request.META:
        auth_parts = request.META['HTTP_AUTHORIZATION'].split(' ')
        if len(auth_parts) == 2:
            auth_type = auth_parts[0].lower()
            if auth_type == 'basic' or auth_type == 'x-basic':
                decoded_parts = None
                try:
                    decoded_parts = base64.standard_b64decode(auth_parts[1]).decode().split(':')
                except TypeError:
                    # is malformed base64
                    decoded_parts = []
                    raise

                if len(decoded_parts) == 2:
                    username = decoded_parts[0]
                    password = decoded_parts[1]

                    try:
                        user = models.User.objects.get(email=username)
                        try:
                            __password_hasher.verify(user.pw_hash, password)
                            return user
                        except argon2.exceptions.VerifyMismatchError:
                            pass
                    except models.User.DoesNotExist:
                        pass
    return None


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
