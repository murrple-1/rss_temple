import os
from typing import Any, Callable

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.http import HttpRequest, HttpResponse

_OUTPUT_FILE: str | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _OUTPUT_FILE

    _OUTPUT_FILE = settings.PROFILING_OUTPUT_FILE


_load_global_settings()


class ProfileMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if (
            _OUTPUT_FILE is not None
            and settings.DEBUG
            and request.GET.get("_profile", "").lower() == "true"
        ):
            _OUTPUT_FILE_DIR = os.path.dirname(_OUTPUT_FILE)
            if _OUTPUT_FILE_DIR != "" and not os.path.isdir(_OUTPUT_FILE_DIR):
                os.makedirs(_OUTPUT_FILE_DIR, 0o755)

            import cProfile

            profile = cProfile.Profile()
            profile.enable()

            response = self.get_response(request)

            profile.disable()

            profile.dump_stats(_OUTPUT_FILE)

            return response
        else:
            return self.get_response(request)
