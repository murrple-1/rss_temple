import re

from django.http import HttpResponse
from django.conf import settings

from api import authenticate

_REALM = settings.REALM
_AUTHENTICATION_DISABLE = settings.AUTHENTICATION_DISABLE


class AuthenticationMiddleware:
    class DisableEntry:
        def __init__(self, path_info_regex_str, method_list):
            self.path_info_regex = re.compile(path_info_regex_str)
            self.method_list = method_list


        def matches(self, request):
            return bool(self.path_info_regex.search(request.path_info) and (
                len(self.method_list) < 1 or request.method in self.method_list))


    def __init__(self, get_response):
        self.get_response = get_response


    def __call__(self, request):
        if not self._should_authenticate(request):
            return self.get_response(request)

        if authenticate.authenticate_http_request(request):
            return self.get_response(request)
        else:
            response = HttpResponse('Authorization failed', status=401)
            # usually, this would be type:"Basic", but that causes popups in browsers, which we want to avoid
            # see:
            # http://loudvchar.blogspot.ca/2010/11/avoiding-browser-popup-for-401.html
            response['WWW-Authenticate'] = 'X-Basic realm="{0}"'.format(
                _REALM) if _REALM else 'X-Basic'
            return response


    def _should_authenticate(self, request):
        if not hasattr(self, '_disable_entries'):
            if _AUTHENTICATION_DISABLE is not None:
                self._disable_entries = []
                for disable_tuple in _AUTHENTICATION_DISABLE:
                    self._disable_entries.append(
                        AuthenticationMiddleware.DisableEntry(
                            *disable_tuple))
            else:
                self._disable_entries = None

        if self._disable_entries is not None:
            for disable_entry in self._disable_entries:
                if disable_entry.matches(request):
                    return False

        return True
