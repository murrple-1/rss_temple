# Setting up Django

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rss_temple.settings")

# django.conf.settings requires these be set, but the value doesn't matter
# for this script
os.environ.setdefault("SECRET_KEY", "<SECRET_KEY>")
os.environ.setdefault("GOOGLE_CLIENT_ID", "<GOOGLE_CLIENT_ID>")

import django

django.setup()

# regularly scheduled programming

import argparse
import time

from .impl import do_subscription, get_first_entry, logger

parser = argparse.ArgumentParser()
args = parser.parse_args()

try:
    while True:
        feed_subscription_progress_entry = get_first_entry()
        if feed_subscription_progress_entry is not None:
            logger().info("starting subscription processing...")
            do_subscription(feed_subscription_progress_entry)
        else:
            logger().info("no subscription process available. sleeping...")
            time.sleep(5)
except Exception:
    logger().exception("loop stopped unexpectedly")
    raise
