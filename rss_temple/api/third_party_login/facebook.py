from django.conf import settings
from django.dispatch import receiver
from django.core.signals import setting_changed

import facebook


_FACEBOOK_TEST_ID = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _FACEBOOK_TEST_ID

    _FACEBOOK_TEST_ID = getattr(settings, 'FACEBOOK_TEST_ID', None)


_load_global_settings()


def get_id(token):
    if _FACEBOOK_TEST_ID is None:  # pragma: ci cover; pragma: remote cover
        graph = facebook.GraphAPI(token)

        profile = None
        try:
            profile = graph.get_object('me', fields='id')
        except facebook.GraphAPIError as e:
            raise ValueError('Facebook Graph API error') from e

        return profile['id']
    else:
        return _FACEBOOK_TEST_ID


def get_id_and_email(token):
    if _FACEBOOK_TEST_ID is None:  # pragma: ci cover; pragma: remote cover
        graph = facebook.GraphAPI(token)

        profile = None
        try:
            profile = graph.get_object('me', fields='id,email')
        except facebook.GraphAPIError as e:
            raise ValueError('Facebook Graph API error') from e

        return profile['id'], profile.get('email', None)
    else:
        return _FACEBOOK_TEST_ID, None
