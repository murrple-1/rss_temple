from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.functions import Now
from django.utils import timezone

from api.models import Feed
from api.tasks import archive_feed_entries


class Command(BaseCommand):
    help = "Mark old feed entries as archived"

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        count = 0
        with transaction.atomic():
            for feed in (
                Feed.objects.filter(archive_update_backoff_until__lte=Now())
                .order_by("archive_update_backoff_until")
                .iterator()
            ):
                count += 1

                archive_feed_entries(
                    feed,
                    timezone.now(),
                    settings.ARCHIVE_TIME_THRESHOLD,
                    settings.ARCHIVE_COUNT_THRESHOLD,
                    settings.ARCHIVE_BACKOFF_SECONDS,
                )

        self.stderr.write(self.style.NOTICE(f"updated {count} feed archives"))
