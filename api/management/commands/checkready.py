from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Run tests to ensure the various dependencies are up"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--no-db-test", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["no_db_test"]:
            self.stderr.write(self.style.NOTICE("testing DB..."))
            self._test_db()
            self.stderr.write(self.style.NOTICE("success"))
        else:
            self.stderr.write(self.style.NOTICE("DB test skipped"))

    def _test_db(self) -> None:
        db_conn = connections["default"]
        try:
            with db_conn.cursor():
                pass
        except OperationalError as e:
            raise CommandError("DB not reachable") from e
