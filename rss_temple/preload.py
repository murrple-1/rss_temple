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
    cache connection is opened -- a connection created here would be
    inherited as a dead socket by every worker.

    This is enforced by `api/tests/test_preload.py`'s
    `WarmUrlResolverForkSafetyTestCase`, which runs the check in a **fresh
    subprocess**, not in-process. That distinction matters and is not
    incidental: `manage.py test` resolves ROOT_URLCONF during Django's
    system checks before any test method runs, so by the time an in-process
    test calls this function the ~975 modules it imports are already sitting
    in `sys.modules` and the call is a no-op cache hit that touches nothing.
    An in-process test watching for a new connection would not see one even
    if a module in that tree opened a connection at import time -- this was
    confirmed by literally injecting `connection.cursor().execute(...)` at
    module scope in a view module and watching an in-process version of this
    test keep passing. If someone "simplifies" the fork-safety tests back
    into an in-process check, they stop testing anything.

    Returns the number of top-level URL patterns, so callers can log that the
    warmup actually did something.
    """
    return len(get_resolver().url_patterns)
