import os

from django.core import mail
from lingua import IsoCode639_3, Language

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
    "Setup the DB as if the various RunPython migration scripts were run"
    Language_.objects.get_or_create(iso639_3="UND", defaults={"name": "UNDEFINED"})
    Language_.objects.bulk_create(
        (
            Language_(
                iso639_3=iso639_3.name, name=Language.from_iso_code_639_3(iso639_3).name
            )
            for iso639_3 in IsoCode639_3
        ),
        ignore_conflicts=True,
    )
