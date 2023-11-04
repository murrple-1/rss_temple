from typing import Any

from django.core.management.base import BaseCommand

from api.tasks import purge_expired_data


class Command(BaseCommand):
    help = "Purge expired data"

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        purge_expired_data()
