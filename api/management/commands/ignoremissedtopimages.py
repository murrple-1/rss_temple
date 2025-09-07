from typing import Any
import datetime

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from api.tasks import ignore_missed_top_images


class Command(BaseCommand):
    help = "Ignore missed top images"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("since")

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        since = datetime.datetime.fromisoformat(options["since"])

        if timezone.is_naive(since):
            since = timezone.make_aware(since)

        ignore_missed_top_images(since)
