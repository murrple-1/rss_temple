import datetime
import hashlib
from typing import Any, Optional

from allauth.account import app_settings as allauth_account_settings

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.cache import caches
from django.core.signals import setting_changed
from django.db.models import Model
from django.dispatch import receiver
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import BasicAuthentication, TokenAuthentication
from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle

from api.models import Token, User

_TOKEN_EXPIRY_INTERVAL: datetime.timedelta
_BASIC_AUTH_MAX_FAILURES_PER_IP: int
_BASIC_AUTH_MAX_FAILURES_PER_USER: int
_BASIC_AUTH_FAILURE_WINDOW: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _TOKEN_EXPIRY_INTERVAL
    global _BASIC_AUTH_MAX_FAILURES_PER_IP
    global _BASIC_AUTH_MAX_FAILURES_PER_USER
    global _BASIC_AUTH_FAILURE_WINDOW

    _TOKEN_EXPIRY_INTERVAL = settings.TOKEN_EXPIRY_INTERVAL
    _BASIC_AUTH_MAX_FAILURES_PER_IP = settings.BASIC_AUTH_MAX_FAILURES_PER_IP
    _BASIC_AUTH_MAX_FAILURES_PER_USER = settings.BASIC_AUTH_MAX_FAILURES_PER_USER
    _BASIC_AUTH_FAILURE_WINDOW = settings.BASIC_AUTH_FAILURE_WINDOW


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
                    raise exceptions.AuthenticationFailed("Token expired")

                token.expires_at = now + _TOKEN_EXPIRY_INTERVAL
                token.save(update_fields=("expires_at",))

            setattr(user, "_token", token)

        return auth_tuple


class ThrottledVerifiedBasicAuthentication(BasicAuthentication):
    """HTTP Basic auth, hardened for use on every endpoint.

    DRF authenticates *before* it checks throttles, so a failed Basic attempt
    is rejected before any throttle class runs. Failed attempts are therefore
    counted (per client IP and per account) and enforced here, before the
    password is hashed. The login serializer's email-verification requirement
    is also applied, since Basic auth bypasses that serializer.
    """

    def authenticate_credentials(
        self, userid: str, password: str, request: Request | None = None
    ) -> tuple[AnonymousUser | AbstractBaseUser, None]:
        cache = caches["throttle"]

        limits: list[tuple[str, int]] = [
            (
                "basic_auth_fail_user_"
                + hashlib.sha256(userid.lower().encode()).hexdigest(),
                _BASIC_AUTH_MAX_FAILURES_PER_USER,
            )
        ]
        if request is not None:
            limits.append(
                (
                    f"basic_auth_fail_ip_{BaseThrottle().get_ident(request)}",
                    _BASIC_AUTH_MAX_FAILURES_PER_IP,
                )
            )

        window_seconds = _BASIC_AUTH_FAILURE_WINDOW.total_seconds()

        # check before authenticating, so rejected attempts don't cost a hash
        if any(cache.get(key, 0) >= max_failures for key, max_failures in limits):
            raise exceptions.Throttled(wait=window_seconds)

        try:
            user, _ = super().authenticate_credentials(userid, password, request)
        except exceptions.AuthenticationFailed:
            for key, _max_failures in limits:
                cache.add(key, 0, timeout=window_seconds)
                cache.incr(key)
            raise

        if (
            allauth_account_settings.EMAIL_VERIFICATION
            == allauth_account_settings.EmailVerificationMethod.MANDATORY
            and not user.emailaddress_set.filter(  # type: ignore[attr-defined]
                email=user.email,
                verified=True,  # type: ignore[attr-defined]
            ).exists()
        ):
            raise exceptions.AuthenticationFailed("E-mail is not verified.")

        return user, None
