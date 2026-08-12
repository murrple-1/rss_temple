"""Pre-fork warmup for the gunicorn arbiter.

Paired with `preload_app = True` in `gunicorn.conf.py`. See the comment there.
"""

from django.urls import get_resolver


def warm_url_resolver() -> int:
    """Force Django's root URL resolver to populate.

    Django resolves ROOT_URLCONF lazily, on the first request. Under
    `preload_app` the arbiter runs django.setup() and loads middleware before
    forking, but NOT this -- so every worker independently imports the whole
    view/serializer tree (~975 modules: api.views, api.serializers, allauth,
    drf_spectacular, silk) after the fork, and none of it is shared.

    Calling this in the arbiter moves those imports before the fork, where
    copy-on-write shares them across workers.

    Safe to call pre-fork: it performs module imports only. No database or
    cache connection is opened, which `api/tests/test_preload.py` asserts --
    a connection created here would be inherited as a dead socket by every
    worker.

    Returns the number of top-level URL patterns, so callers can log that the
    warmup actually did something.
    """
    return len(get_resolver().url_patterns)
