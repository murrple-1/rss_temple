import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError

_logger = logging.getLogger("rss_temple")


class Command(BaseCommand):
    help = "TODO help text"

    def add_arguments(self, parser):
        parser.add_argument("--skip-db-test", action="store_true")

    def handle(self, *args, **options):
        if not options.get("skip_db_test", False):
            _logger.info("testing DB...")
            self._test_db()
            _logger.info("success")

    def _test_db(self):
        db_conn = connections["default"]
        try:
            c = db_conn.cursor()
        except OperationalError as e:
            raise CommandError("DB not reachable") from e
