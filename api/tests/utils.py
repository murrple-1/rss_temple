import os

from django.core import mail


def debug_print_last_email():
    if os.getenv("TEST_EMAILS_CONSOLE") == "true":
        print(getattr(mail, "outbox")[-1].message())
