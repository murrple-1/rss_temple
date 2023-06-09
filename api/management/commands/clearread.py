from typing import Any

from django.core.management.base import BaseCommand

from api.models import ReadFeedEntryUserMapping


class Command(BaseCommand):
    help = "Clear all of the 'read' states"

    def handle(self, *args: Any, **options: Any) -> str | None:
        count, _ = ReadFeedEntryUserMapping.objects.all().delete()

        self.stderr.write(self.style.NOTICE(f"{count} entries deleted"))
