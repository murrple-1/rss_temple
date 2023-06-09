from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from google.auth.transport import requests
from google.oauth2 import id_token

_GOOGLE_CLIENT_ID: str
_GOOGLE_TEST_ID: str | None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _GOOGLE_CLIENT_ID
    global _GOOGLE_TEST_ID

    _GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
    _GOOGLE_TEST_ID = getattr(settings, "GOOGLE_TEST_ID", None)


_load_global_settings()


def get_id(token: str):
    if _GOOGLE_TEST_ID is None:  # pragma: testing-google
        idinfo = id_token.verify_oauth2_token(
            token, requests.Request(), _GOOGLE_CLIENT_ID
        )
        return idinfo["sub"]
    else:
        return _GOOGLE_TEST_ID


def get_id_and_email(token: str):
    if _GOOGLE_TEST_ID is None:  # pragma: testing-google
        idinfo = id_token.verify_oauth2_token(
            token, requests.Request(), _GOOGLE_CLIENT_ID
        )
        return idinfo["sub"], idinfo.get("email", None)
    else:
        return _GOOGLE_TEST_ID, None
