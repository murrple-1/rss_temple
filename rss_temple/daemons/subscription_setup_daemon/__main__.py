import time
import argparse
import logging

from . import get_first_entry, do_subscription, logger


def _subscription_loop():
    while True:
        feed_subscription_progress_entry = get_first_entry()
        if feed_subscription_progress_entry is not None:
            logger().info('starting subscription processing...')
            do_subscription(feed_subscription_progress_entry)
        else:
            logger().info('no subscription process available. sleeping...')
            time.sleep(5)
            continue


parser = argparse.ArgumentParser()
args = parser.parse_args()

logger().setLevel(logging.DEBUG)

try:
    _subscription_loop()
except Exception:
    logger().exception('loop stopped unexpectedly')
    raise
