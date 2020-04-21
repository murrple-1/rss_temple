from django.conf import settings
from django.dispatch import receiver
from django.core.signals import setting_changed

from google.oauth2 import id_token
from google.auth.transport import requests


_GOOGLE_CLIENT_ID = None
_GOOGLE_TEST_ID = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _GOOGLE_CLIENT_ID
    global _GOOGLE_TEST_ID

    _GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
    _GOOGLE_TEST_ID = getattr(settings, 'GOOGLE_TEST_ID', None)


_load_global_settings()


def get_id(token):
    if _GOOGLE_TEST_ID is None:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), _GOOGLE_CLIENT_ID)
        return idinfo['sub']
    else:
        return _GOOGLE_TEST_ID


def get_id_and_email(token):
    if _GOOGLE_TEST_ID is None:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), _GOOGLE_CLIENT_ID)
        return idinfo['sub'], idinfo.get('email', None)
    else:
        return _GOOGLE_TEST_ID, None
