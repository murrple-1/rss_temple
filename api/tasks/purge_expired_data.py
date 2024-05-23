import logging
from importlib import import_module
from typing import cast

from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase
from django.db import transaction
from django.db.models.functions import Now

from api.models import Captcha, Token

_logger = logging.getLogger("rss_temple")


def purge_expired_data() -> None:
    with transaction.atomic():
        _, deletes = Captcha.objects.filter(expires_at__lte=Now()).delete()
        captcha_count = deletes.get("api.Captcha", 0)
        _logger.info("removed %d captchas", captcha_count)

        _, deletes = Token.objects.filter(expires_at__lte=Now()).delete()
        token_count = deletes.get("api.Token", 0)
        _logger.info("removed %d tokens", token_count)

    engine = import_module(settings.SESSION_ENGINE)
    SessionStore = cast(type[SessionBase], engine.SessionStore)
    try:
        SessionStore.clear_expired()
    except NotImplementedError:  # pragma: no cover
        _logger.warning(
            "Session engine '%s' doesn't support clearing expired sessions.",
            settings.SESSION_ENGINE,
        )
