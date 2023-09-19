import datetime
from typing import Any

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.signals import setting_changed
from django.db.models import Model
from django.dispatch import receiver
from django.utils import timezone
from rest_framework.serializers import Serializer

_TOKEN_EXPIRY_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _TOKEN_EXPIRY_INTERVAL

    _TOKEN_EXPIRY_INTERVAL = settings.TOKEN_EXPIRY_INTERVAL


_load_global_settings()


def create_token(
    token_model: type[Model],
    user: AnonymousUser | AbstractBaseUser,
    serializer: Serializer,
):
    return token_model.objects.create(
        user=user, expires_at=(timezone.now() + _TOKEN_EXPIRY_INTERVAL)
    )
