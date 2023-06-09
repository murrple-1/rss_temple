import datetime
import re
from typing import Any, Callable

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from ipware import get_client_ip


class _EnableEntry:
    def __init__(
        self,
        id_: str,
        request_matchers: list[tuple[str, list[str]]],
        max_requests: int,
        interval: int,
    ):
        self.id = id_
        self.request_matchers = [
            (re.compile(request_matcher[0]), request_matcher[1])
            for request_matcher in request_matchers
        ]
        self.max_requests = max_requests
        if type(interval) in (int, float):
            self.interval_seconds = interval
        elif isinstance(interval, datetime.timedelta):
            self.interval_seconds = interval.total_seconds()

    def matches(self, request):
        for request_matcher in self.request_matchers:
            path_info_regex, method_list = request_matcher
            if path_info_regex.search(request.path_info) and (
                len(method_list) < 1 or request.method in method_list
            ):
                return True

        return False


_enable_entries: list[_EnableEntry]


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _enable_entries

    THROTTLE_ENABLE = settings.THROTTLE_ENABLE
    if THROTTLE_ENABLE is not None:
        _enable_entries = [
            _EnableEntry(*enable_tuple) for enable_tuple in THROTTLE_ENABLE
        ]
    else:
        _enable_entries = []


_load_global_settings()


class ThrottleMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        client_ip, _is_routable = get_client_ip(request)
        if client_ip is None:
            return HttpResponseBadRequest("client IP missing")

        entry_id, max_requests, interval_seconds = self._throttle_params(request)
        if (
            entry_id is not None
            and max_requests is not None
            and interval_seconds is not None
        ):
            cache = caches["throttle"]
            cache_key = f"request_count:{entry_id}:{client_ip}"

            request_count: int
            if not _is_dummy_cache(cache):
                request_count = cache.get_or_set(cache_key, 0, interval_seconds)
                cache.incr(cache_key)
                request_count += 1
            else:
                request_count = 1

            response: HttpResponse
            if request_count <= max_requests:
                response = self.get_response(request)
            else:
                response = HttpResponse(status=429)

            return response
        else:
            return self.get_response(request)

    def _throttle_params(self, request: HttpRequest):
        assert _enable_entries is not None
        for enable_entry in _enable_entries:
            if enable_entry.matches(request):
                return (
                    enable_entry.id,
                    enable_entry.max_requests,
                    enable_entry.interval_seconds,
                )

        return None, None, None


def _is_dummy_cache(cache: BaseCache):
    from django.core.cache.backends.dummy import DummyCache

    return isinstance(cache, DummyCache)
