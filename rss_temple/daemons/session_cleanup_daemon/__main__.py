import time
import argparse
import logging

import filelock

from . import cleanup, logger


parser = argparse.ArgumentParser()
parser.add_argument('-f', '--force-now', help='Clear the expired sessions immediately, then exit', action='store_true')
args = parser.parse_args()

logger().setLevel(logging.DEBUG)

if not args.force_now:
    lock = filelock.FileLock('session_cleanup_daemon.lock')
    try:
        with lock.acquire(timeout=1):
            while True:
                cleanup()
                time.sleep(60 * 60 * 24)
    except filelock.Timeout:
        logger().info('only 1 process allowed at a time - lock file already held')
    except Exception:
        logger().exception('loop stopped unexpectedly')
        raise
else:
    cleanup()
