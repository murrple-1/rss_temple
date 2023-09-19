import datetime
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.signals import setting_changed
from django.db.models import Model
from django.dispatch import receiver
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication
from rest_framework.request import Request

from api.models import Token, User

_TOKEN_EXPIRY_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _TOKEN_EXPIRY_INTERVAL

    _TOKEN_EXPIRY_INTERVAL = settings.TOKEN_EXPIRY_INTERVAL


_load_global_settings()


class ExpiringTokenAuthentication(TokenAuthentication):
    model = Token

    def authenticate(
        self, request: Request
    ) -> Optional[tuple[AnonymousUser | AbstractBaseUser, Model]]:
        auth_tuple = super().authenticate(request)

        if auth_tuple is not None:
            user, token = auth_tuple
            assert isinstance(user, User)
            assert isinstance(token, Token)

            if token.expires_at is not None:
                now = timezone.now()
                if token.expires_at <= now:
                    token.delete()
                    raise exceptions.AuthenticationFailed("Token expired")

                token.expires_at = now + _TOKEN_EXPIRY_INTERVAL
                token.save(update_fields=("expires_at",))

            user.token = token

        return auth_tuple
