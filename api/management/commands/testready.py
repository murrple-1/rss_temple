import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run tests to ensure the various dependencies are up"

    def add_arguments(self, parser):
        parser.add_argument("--no-db-test", action="store_true")

    def handle(self, *args, **options):
        if not options["no_db_test"]:
            logger.info("testing DB...")
            self._test_db()
            logger.info("success")
        else:
            logger.info("DB test skipped")

    def _test_db(self) -> None:
        db_conn = connections["default"]
        try:
            with db_conn.cursor():
                pass
        except OperationalError as e:
            raise CommandError("DB not reachable") from e
