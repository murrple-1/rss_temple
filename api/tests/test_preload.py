import os
import subprocess
import sys

from django.conf import settings
from django.test import TestCase
from django.urls import get_resolver


class WarmUrlResolverTestCase(TestCase):
    def test_populates_the_resolver_cache(self):
        from rss_temple.preload import warm_url_resolver

        resolver = get_resolver()
        # `url_patterns` is a cached_property; drop it so we can observe it being filled.
        resolver.__dict__.pop("url_patterns", None)
        self.assertNotIn("url_patterns", resolver.__dict__)

        count = warm_url_resolver()

        self.assertIn("url_patterns", get_resolver().__dict__)
        self.assertGreater(count, 0)

    def test_is_idempotent(self):
        from rss_temple.preload import warm_url_resolver

        first = warm_url_resolver()
        second = warm_url_resolver()
        self.assertEqual(first, second)
        # Pin both calls to the actual number of root URL patterns, not just to
        # each other -- otherwise a neutered `warm_url_resolver()` (e.g. one
        # hardcoded to `return 1`) would still pass this test as long as it
        # returned the same constant twice.
        self.assertEqual(first, len(get_resolver().url_patterns))


# These two scripts are run in a *fresh subprocess*, not in-process, and that is
# the entire point of this test class.
#
# `manage.py test` runs Django's system checks before any test method executes,
# and those checks already resolve ROOT_URLCONF. So by the time an in-process
# test body calls `warm_url_resolver()`, the ~975 modules it imports
# (`api.views`, `api.serializers`, `allauth`, `drf_spectacular`, `silk`, ...)
# are already sitting in `sys.modules` from the system-check pass, and
# re-resolving does not re-execute their module-level code. An in-process test
# asserting "no connection was opened" is therefore watching a cache hit that
# touches nothing -- it cannot detect a module-level `connection.cursor().execute(...)`
# or similar, no matter how it's written. (An earlier version of this file had
# exactly that defect, confirmed by literally injecting such a statement into a
# view module and watching the in-process test still pass. See the task-7 fix
# round in the report for how that was found.)
#
# Only a fresh interpreter -- one that has not yet resolved the URLconf -- can
# observe the import actually happening. Hence: subprocess.
_DATABASE_FORK_SAFETY_SCRIPT = """
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rss_temple.settings")
os.environ.setdefault("APP_SECRET_KEY", "x" * 50)

import django

django.setup()

from django.db import connection

if connection.connection is not None:
    print(
        "FAIL: a database connection was already open before warm_url_resolver() ran",
        file=sys.stderr,
    )
    sys.exit(1)

from rss_temple.preload import warm_url_resolver

count = warm_url_resolver()

if connection.connection is not None:
    print(
        f"FAIL: warm_url_resolver() opened a database connection (resolved {count} pattern(s))",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"OK: resolved {count} pattern(s), no database connection opened")
"""

_CACHE_FORK_SAFETY_SCRIPT = """
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rss_temple.settings")
os.environ.setdefault("APP_SECRET_KEY", "x" * 50)

import django

django.setup()

from django.core.cache import caches

ALIASES = ("default", "stable_query", "captcha", "throttle")


def snapshot():
    # django_redis.client.DefaultClient keeps a list of lazily-created
    # redis.Redis clients in `_clients`, one per configured server, each
    # None until get_client() is called on first actual .get()/.set().
    return {alias: list(caches[alias].client._clients) for alias in ALIASES}


before = snapshot()
for alias, clients in before.items():
    if any(c is not None for c in clients):
        print(
            f"FAIL: {alias} cache already connected before warm_url_resolver() ran: {clients}",
            file=sys.stderr,
        )
        sys.exit(1)

from rss_temple.preload import warm_url_resolver

count = warm_url_resolver()

after = snapshot()
for alias, clients in after.items():
    if any(c is not None for c in clients):
        print(
            f"FAIL: {alias} cache connected while warming the resolver "
            f"(resolved {count} pattern(s)): {clients}",
            file=sys.stderr,
        )
        sys.exit(1)

print(f"OK: resolved {count} pattern(s), no cache client connected")
"""


class WarmUrlResolverForkSafetyTestCase(TestCase):
    """Fork-safety checks for `warm_url_resolver()`, run in a fresh subprocess.

    See the module-level comment above the two script constants for why this
    cannot be done in-process.
    """

    def _run_in_subprocess(
        self, script: str, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = "rss_temple.settings"
        env.setdefault("APP_SECRET_KEY", "x" * 50)
        env["PYTHONPATH"] = str(settings.BASE_DIR)
        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(settings.BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_does_not_open_a_database_connection_at_import(self):
        result = self._run_in_subprocess(_DATABASE_FORK_SAFETY_SCRIPT)

        self.assertEqual(
            result.returncode,
            0,
            "warming the URL resolver opened a database connection in a fresh "
            "process; a connection opened by a module at import time would be "
            "inherited as a dead socket by every forked gunicorn worker.\n"
            f"--- subprocess stdout ---\n{result.stdout}\n"
            f"--- subprocess stderr ---\n{result.stderr}",
        )

    def test_does_not_open_a_cache_connection_at_import(self):
        # APP_IN_DOCKER=true so the subprocess configures the real
        # django-redis-backed CACHES (this test's whole point is to check the
        # redis client construction path), not the local LocMemCache fallback
        # that settings.py selects otherwise. No Redis/Valkey server needs to
        # be running: django-redis connects lazily, so the check is that
        # resolution never *tries* to connect, not that it succeeds.
        result = self._run_in_subprocess(
            _CACHE_FORK_SAFETY_SCRIPT, extra_env={"APP_IN_DOCKER": "true"}
        )

        self.assertEqual(
            result.returncode,
            0,
            "warming the URL resolver connected a redis cache client in a "
            "fresh process; a connection opened by a module at import time "
            "would be inherited as a dead socket by every forked gunicorn "
            "worker.\n"
            f"--- subprocess stdout ---\n{result.stdout}\n"
            f"--- subprocess stderr ---\n{result.stderr}",
        )
