import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1
capture_output = True
accesslog = "-"

# Load the application once in the master process and fork, so
# django.setup() + middleware imports are shared copy-on-write instead of
# duplicated across `cpu_count() * 2 + 1` workers (measured ~27MB across 4
# workers, ~11% of cold RSS). Django resolves ROOT_URLCONF lazily on first
# request, so the larger view/serializer import cost is still paid per-worker
# after fork; sharing that too would require warming the URLConf pre-fork.
# Requires that nothing opens a database or cache connection at import time,
# since connections do not survive fork().
preload_app = True
