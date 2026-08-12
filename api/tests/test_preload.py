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

    def test_does_not_open_a_database_connection(self):
        # NOTE: the brief's original version of this test called
        # `connection.close()` then asserted `connection.connection is None`.
        # That doesn't work in *this* project's default test configuration:
        # Django's `TestCase` wraps every test in an outer `atomic()` block
        # (opened in `setUpClass`, before this method body ever runs), and
        # `django.db.backends.sqlite3.base.DatabaseWrapper.close()` is a
        # deliberate no-op for in-memory databases ("closing the connection
        # destroys the database... ignore close requests"). Verified
        # empirically: `connection.connection` is already a live
        # `sqlite3.Connection` at the top of the test method, and calling
        # `.close()` does not clear it. So the brief's version would fail
        # unconditionally, independent of whether `warm_url_resolver` behaves
        # correctly.
        #
        # This version tests the same real invariant -- warming the resolver
        # must not establish a *new* database connection, since one opened
        # here would be inherited as a dead socket by every forked gunicorn
        # worker -- without depending on `close()`/`None` semantics that
        # don't hold for this test DB backend.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from rss_temple.preload import warm_url_resolver

        connection.ensure_connection()
        connection_before = connection.connection
        self.assertIsNotNone(connection_before)

        with CaptureQueriesContext(connection) as ctx:
            warm_url_resolver()

        self.assertIs(
            connection.connection,
            connection_before,
            "warming the URL resolver opened a new database connection; a "
            "connection opened by a module at import time would be "
            "inherited as a dead socket by every forked gunicorn worker",
        )
        self.assertEqual(
            ctx.captured_queries,
            [],
            "warming the URL resolver executed a database query",
        )
