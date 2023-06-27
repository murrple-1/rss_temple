from functools import wraps
from typing import Any

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.http import HttpRequest, HttpResponse

_REALM: str | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _REALM

    _REALM = settings.REALM


_load_global_settings()


def requires_authenticated_user():
    def decorator(view_func):
        @wraps(view_func)
        def _wrapper_view(request: HttpRequest, *args, **kwargs):
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)

            response = HttpResponse("Authorization failed", status=401)
            # usually, this would be type:"Basic", but that causes popups in browsers, which we want to avoid
            # see:
            # http://loudvchar.blogspot.ca/2010/11/avoiding-browser-popup-for-401.html
            response["WWW-Authenticate"] = (
                f'X-Basic realm="{_REALM}"' if _REALM else "X-Basic"
            )
            return response

        return _wrapper_view

    return decorator
