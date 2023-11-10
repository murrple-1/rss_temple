import datetime
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.core.signals import setting_changed
from django.dispatch import receiver

from api.tasks import label_users

_LABELING_EXPIRY_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _LABELING_EXPIRY_INTERVAL

    _LABELING_EXPIRY_INTERVAL = settings.LABELING_EXPIRY_INTERVAL


_load_global_settings()


class Command(BaseCommand):
    help = "Calculate the labels of users"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("--top-x", type=int, default=10)

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        label_users(options["top_x"], _LABELING_EXPIRY_INTERVAL)
