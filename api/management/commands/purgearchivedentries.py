import argparse
import datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.utils import timezone

from api.models import FeedEntry


class Command(BaseCommand):
    help = (
        "Delete archived feed entries published before a cutoff (3 years ago by "
        "default). Entries that someone has favorited are kept. Dry-run by "
        "default."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        cutoff_group = parser.add_mutually_exclusive_group()
        cutoff_group.add_argument("--older-than-years", type=int, default=3)
        cutoff_group.add_argument(
            "--before",
            type=datetime.date.fromisoformat,
            help="ISO date (YYYY-MM-DD); overrides --older-than-years",
        )
        parser.add_argument(
            "--dry-run", action=argparse.BooleanOptionalAction, default=True
        )
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args: Any, **options: Any) -> None:
        older_than_years: int = options["older_than_years"]
        before: datetime.date | None = options["before"]
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]

        if batch_size < 1:
            raise CommandError(f"--batch-size must be at least 1, got {batch_size}")

        now = timezone.now()
        if before is not None:
            cutoff = datetime.datetime.combine(
                before, datetime.time.min, tzinfo=datetime.timezone.utc
            )
        else:
            if older_than_years < 1:
                raise CommandError(
                    f"--older-than-years must be at least 1, got {older_than_years}"
                )
            cutoff = now - relativedelta(years=older_than_years)

        if cutoff > now:
            raise CommandError(f"cutoff {cutoff.isoformat()} is in the future")

        qs = FeedEntry.objects.filter(
            is_archived=True, published_at__lt=cutoff
        ).exclude(favorite_user_set__isnull=False)

        self.stderr.write(self.style.NOTICE(f"cutoff: {cutoff.isoformat()}"))
        self.stderr.write(self.style.NOTICE(f"matching entries: {qs.count()}"))

        if dry_run:
            self.stderr.write(
                self.style.WARNING("dry run; nothing deleted. pass --no-dry-run to act")
            )
            return

        deleted = 0
        while True:
            with transaction.atomic():
                batch_uuids = list(qs.values_list("uuid", flat=True)[:batch_size])
                if not batch_uuids:
                    break
                _, deleted_by_model = FeedEntry.objects.filter(
                    uuid__in=batch_uuids
                ).delete()
                deleted += deleted_by_model.get(FeedEntry._meta.label, 0)

        self.stderr.write(self.style.SUCCESS(f"deleted {deleted} feed entry(s)"))
