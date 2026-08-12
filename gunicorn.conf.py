import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1
capture_output = True
accesslog = "-"

# Load the application once in the master process and fork, so
# django.setup() + middleware imports are shared copy-on-write instead of
# duplicated across `cpu_count() * 2 + 1` workers (measured ~27MB across 4
# workers, ~11% of cold RSS). Django resolves ROOT_URLCONF lazily on first
# request, so the larger view/serializer import cost was still paid per-worker
# after fork, and shared none of it -- see `on_starting` below, which closes
# that gap by warming the URLConf pre-fork too.
# Requires that nothing opens a database or cache connection at import time,
# since connections do not survive fork(). Checked for the modules `preload_app`
# alone reaches in task 6's audit, and re-checked for the larger set `on_starting`
# below additionally pulls in, in task 7's audit. Both are enforced by
# `api/tests/test_preload.py`'s `WarmUrlResolverForkSafetyTestCase`, which runs in
# a fresh subprocess -- see that test module and `rss_temple/preload.py`'s
# docstring for why it must be a subprocess and not an in-process check.
#
# Operational consequence: with `preload_app` on, the master process holds the
# loaded application code, so `kill -HUP <master pid>` (gunicorn's usual
# "reload workers with new code" signal) no longer picks up a new deploy --
# workers restart but re-inherit the master's already-loaded (old) code.
# Deploying a code change now requires restarting the master/container, not
# signalling it.
preload_app = True


def on_starting(server):
    # DO NOT DELETE -- this looks like a no-op (nothing here reads its own
    # return value, and gunicorn never calls it directly), but it is load-
    # bearing: it is the second half of the `preload_app` memory win above,
    # and without it most of that win doesn't happen.
    #
    # `on_starting` runs in the arbiter (master) process, strictly after
    # `preload_app` has already run `django.setup()` and loaded middleware
    # (`Arbiter.setup()` calls `self.app.wsgi()` synchronously inside
    # `Arbiter.__init__`, before `.run()` -- and hence before this hook --
    # is ever invoked) and strictly before any worker is forked (`Arbiter.run()`
    # calls `self.start()`, which fires this hook, and only afterwards calls
    # `self.manage_workers()` -> `spawn_workers()` -> `fork()`). Verified by
    # reading the installed gunicorn's `arbiter.py` rather than trusting this
    # comment -- confirm again after any gunicorn upgrade, since this hook is
    # only useful if that ordering holds.
    #
    # That window matters because Django resolves `ROOT_URLCONF` lazily, on
    # the first request. `preload_app` alone shares only `django.setup()` and
    # middleware imports across workers; every worker still independently
    # imports the entire view/serializer tree (~975 modules: `api.views`,
    # `api.serializers`, `allauth`, `drf_spectacular`, `silk`) the first time
    # it handles a request, *after* it has already forked, so none of that
    # import cost is shared. Forcing the resolution here, in the one window
    # where the app is loaded but workers don't exist yet, moves those
    # imports before the fork, where copy-on-write shares them.
    #
    # Deferred (function-body) import on purpose: this file is read by
    # gunicorn before Django is configured, so a module-level
    # `from rss_temple.preload import warm_url_resolver` would fail at
    # gunicorn startup, before the arbiter even exists to run this hook.
    from rss_temple.preload import warm_url_resolver

    count = warm_url_resolver()
    server.log.info("pre-fork URL resolver warmup: %d root pattern(s)", count)
