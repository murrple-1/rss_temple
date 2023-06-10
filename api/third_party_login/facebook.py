from typing import Any

import facebook
from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver

_FACEBOOK_TEST_ID: str | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _FACEBOOK_TEST_ID

    _FACEBOOK_TEST_ID = getattr(settings, "FACEBOOK_TEST_ID", None)


_load_global_settings()


def get_id(token: str) -> str:
    if _FACEBOOK_TEST_ID is None:  # pragma: testing-facebook
        graph = facebook.GraphAPI(token)

        profile: dict[str, Any]
        try:
            profile = graph.get_object("me", fields="id")
        except facebook.GraphAPIError as e:
            raise ValueError("Facebook Graph API error") from e

        return profile["id"]
    else:
        return _FACEBOOK_TEST_ID


def get_id_and_email(token: str) -> tuple[str, str | None]:
    if _FACEBOOK_TEST_ID is None:  # pragma: testing-facebook
        graph = facebook.GraphAPI(token)

        profile: dict[str, Any]
        try:
            profile = graph.get_object("me", fields="id,email")
        except facebook.GraphAPIError as e:
            raise ValueError("Facebook Graph API error") from e

        return profile["id"], profile.get("email", None)
    else:
        return _FACEBOOK_TEST_ID, None
