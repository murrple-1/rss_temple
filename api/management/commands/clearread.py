import uuid
from typing import Any

from django.core.cache import BaseCache, caches
from django.core.management.base import BaseCommand, CommandParser
from django.db.models import QuerySet

from api.cache_utils.read_feed_entry_uuids import delete_read_feed_entry_uuids_cache
from api.models import ReadFeedEntryUserMapping, User


class Command(BaseCommand):
    help = "Clear all of the 'read' states"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-u", "--user-uuid", type=uuid.UUID)

    def handle(self, *args: Any, **options: Any) -> None:
        qs: QuerySet[ReadFeedEntryUserMapping]
        users: QuerySet[User]
        if (user_uuid := options["user_uuid"]) is not None:
            qs = ReadFeedEntryUserMapping.objects.filter(user_id=user_uuid)
            users = User.objects.filter(uuid=user_uuid)
        else:
            qs = ReadFeedEntryUserMapping.objects.all()
            users = User.objects.all()

        cache: BaseCache = caches["default"]

        for user in users.iterator():
            delete_read_feed_entry_uuids_cache(user, cache)

        count, _ = qs.delete()

        self.stderr.write(self.style.NOTICE(f"{count} entries deleted"))
