import re

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.http import HttpResponse

from api import authenticate


class _DisableEntry:
    def __init__(self, path_info_regex_str, method_list):
        self.path_info_regex = re.compile(path_info_regex_str)
        self.method_list = method_list

    def matches(self, request):
        return bool(
            self.path_info_regex.search(request.path_info)
            and (len(self.method_list) < 1 or request.method in self.method_list)
        )


_REALM = None

_disable_entries = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _REALM
    global _disable_entries

    _REALM = settings.REALM

    AUTHENTICATION_DISABLE = settings.AUTHENTICATION_DISABLE
    if AUTHENTICATION_DISABLE is not None:
        _disable_entries = [
            _DisableEntry(*disable_tuple) for disable_tuple in AUTHENTICATION_DISABLE
        ]
    else:
        _disable_entries = []


_load_global_settings()


class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._should_authenticate(request):
            return self.get_response(request)

        if authenticate.authenticate_http_request(request):
            return self.get_response(request)
        else:
            response = HttpResponse("Authorization failed", status=401)
            # usually, this would be type:"Basic", but that causes popups in browsers, which we want to avoid
            # see:
            # http://loudvchar.blogspot.ca/2010/11/avoiding-browser-popup-for-401.html
            response["WWW-Authenticate"] = (
                f'X-Basic realm="{_REALM}"' if _REALM else "X-Basic"
            )
            return response

    def _should_authenticate(self, request):
        for disable_entry in _disable_entries:
            if disable_entry.matches(request):
                return False

        return True
