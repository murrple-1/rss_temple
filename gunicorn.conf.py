import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1
capture_output = True
accesslog = "-"

# Load the application once in the master process and fork, so the ~126MB
# per-worker Django import cost is shared copy-on-write rather than duplicated
# across `cpu_count() * 2 + 1` workers. Requires that nothing opens a database
# or cache connection at import time, since connections do not survive fork().
preload_app = True
