from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from api.tasks import label_feeds


class Command(BaseCommand):
    help = "Calculate the labels of feeds"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("--top-x", type=int, default=3)

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        label_feeds(options["top_x"], settings.LABELING_EXPIRY_INTERVAL)
