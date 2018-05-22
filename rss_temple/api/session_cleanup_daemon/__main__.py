# Setting up Django

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rss_temple.settings')

# django.conf.settings requires these be set, but the value doesn't matter
# for this script
os.environ.setdefault('SECRET_KEY', '<SECRET_KEY>')

import django

django.setup()

from . import cleanup, logger

parser = argparse.ArgumentParser()
parser.add_argument(
    '-f',
    '--force-now',
    help='Clear the expired sessions immediately, then exit',
    action='store_true',
    dest='runNow')
args = parser.parse_args()

if not args.runNow:
    lock = filelock.FileLock('session_cleanup_daemon.lock')
    try:
        with lock.acquire(timeout=1):
            while True:
                cleanup()
                time.sleep(60 * 60 * 24)
    except filelock.Timeout:
        logger().info('only 1 process allowed at a time - lock file already held')
    except Exception:
        logger().exception('cleanup loop stopped unexpectedly')
        raise
else:
    cleanup()
