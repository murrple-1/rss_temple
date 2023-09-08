import datetime
import secrets

from django.test import TestCase
from django.utils import timezone

from api.django_extensions import bulk_create_iter


class DjangoExtensionsTestCase(TestCase):
    def test_bulk_create_iter(self):
        from api.models import Captcha

        bulk_create_iter(
            (
                Captcha(
                    key=secrets.token_urlsafe(32),
                    seed=secrets.token_hex(32),
                    expires_at=(timezone.now() + datetime.timedelta(minutes=5)),
                )
                for _ in range(100)
            ),
            Captcha,
            batch_size=10,
        )
