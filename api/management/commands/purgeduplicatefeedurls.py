from typing import Any

from django.core.management.base import BaseCommand

from api.tasks import purge_duplicate_feed_urls


class Command(BaseCommand):
    help = "Purge duplicated feed URLs, if they get into the DB somehow"

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        purge_duplicate_feed_urls()
