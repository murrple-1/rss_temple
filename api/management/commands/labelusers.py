from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from api.tasks import label_users


class Command(BaseCommand):
    help = "Calculate the labels of users"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("--top-x", type=int, default=10)

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        label_users(options["top_x"], settings.LABELING_EXPIRY_INTERVAL)
