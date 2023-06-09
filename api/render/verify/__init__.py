from typing import Any

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver

from api import render

_VERIFY_URL_FORMAT: str


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _VERIFY_URL_FORMAT

    _VERIFY_URL_FORMAT = settings.VERIFY_URL_FORMAT


_load_global_settings()


def plain_text(verify_token):
    context = {
        "verify_url": _VERIFY_URL_FORMAT.format(verify_token=verify_token),
    }

    return render.to_text("verify/templates/plain_text.txt", context)


def html_text(verify_token):
    context = {
        "verify_url": _VERIFY_URL_FORMAT.format(verify_token=verify_token),
    }

    return render.to_html("verify/templates/html_text.html", context)


def subject():
    context = {}

    return render.to_text("verify/templates/subject.txt", context)
