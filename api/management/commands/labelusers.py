from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.tasks import label_users


class Command(BaseCommand):
    help = "Calculate the labels of users"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("--top-x", type=int, default=10)
        parser.add_argument(
            "--sleep-seconds", type=float, default=60.0 * 60.0 * 24.0
        )  # 24 hours
        parser.add_argument("--single-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        label_users(options["top_x"])
