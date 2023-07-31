import uuid
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import QuerySet

from api.models import ReadFeedEntryUserMapping


class Command(BaseCommand):
    help = "Clear all of the 'read' states"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-u", "--user-uuid", type=uuid.UUID)

    def handle(self, *args: Any, **options: Any) -> None:
        qs: QuerySet[ReadFeedEntryUserMapping]
        if options["user_uuid"] is not None:
            qs = ReadFeedEntryUserMapping.objects.filter(user_id=options["user_uuid"])
        else:
            qs = ReadFeedEntryUserMapping.objects.all()

        count, _ = qs.delete()

        self.stderr.write(self.style.NOTICE(f"{count} entries deleted"))
