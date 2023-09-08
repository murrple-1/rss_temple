from typing import Any

from django.core.management.base import BaseCommand

from api.models import User


class Command(BaseCommand):
    help = "Reset the read feed entry counter on users"

    def handle(self, *args: Any, **options: Any) -> None:
        for user in User.objects.all().iterator():
            user.read_feed_entries_counter = user.read_feed_entries.count()
            user.save(update_fields=("read_feed_entries_counter",))
