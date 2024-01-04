import os

from django.core import mail
from lingua import Language

from api.models import Language as Language_


def debug_print_last_email() -> None:
    if os.getenv("TEST_EMAILS_CONSOLE") == "true":
        print(getattr(mail, "outbox")[-1].message())


def reusable_captcha_key() -> str:
    # generated by `secrets.token_urlsafe()`
    return "XOuZynTK0uP3jAhN2rZ9JkC6tnSLmXidLkjqIxgoHU8"


def reusable_captcha_seed() -> str:
    # generated by `secrets.token_hex()`
    return "66ba106a3612438180e5b1711dd28cd2dc9365c107960f43c28c1477c27f1f40"


def db_migrations_state():
    "Setup the DB as-if the various RunPython migration scripts were run"
    Language_.objects.get_or_create(
        iso639_3="UND", defaults={"iso639_1": "UN", "name": "UNDEFINED"}
    )
    Language_.objects.bulk_create(
        (
            Language_(
                iso639_3=l.iso_code_639_3.name,
                iso639_1=l.iso_code_639_1.name,
                name=l.name,
            )
            for l in Language.all()
        ),
        ignore_conflicts=True,
    )


def throttling_monkey_patch():
    from rest_framework.throttling import SimpleRateThrottle

    def _allow_request(self, request, view):
        return True

    setattr(SimpleRateThrottle, "allow_request", _allow_request)
