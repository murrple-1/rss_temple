import argparse
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from api.models import ClassifierLabelFeedEntryVote, User


class Command(BaseCommand):
    help = (
        "Delete classifier label votes belonging to a single account. Intended for "
        "removing bulk-import votes that were applied by a script rather than by "
        "users. Dry-run by default."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--user-email", required=True)
        parser.add_argument(
            "--dry-run", action=argparse.BooleanOptionalAction, default=True
        )
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args: Any, **options: Any) -> None:
        user_email: str = options["user_email"]
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]

        if batch_size < 1:
            raise CommandError(f"--batch-size must be at least 1, got {batch_size}")

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            raise CommandError(f"no user with email '{user_email}'")

        qs = ClassifierLabelFeedEntryVote.objects.filter(user=user)

        breakdown = Counter(
            qs.values_list("classifier_label__text", flat=True).iterator()
        )
        total = sum(breakdown.values())

        for label_text, count in breakdown.most_common():
            self.stderr.write(self.style.NOTICE(f"{label_text}: {count}"))
        self.stderr.write(self.style.NOTICE(f"total: {total}"))

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
                count, _ = ClassifierLabelFeedEntryVote.objects.filter(
                    uuid__in=batch_uuids
                ).delete()
                deleted += count

        self.stderr.write(self.style.SUCCESS(f"deleted {deleted} vote(s)"))
        self.stderr.write(
            self.style.NOTICE(
                "classifier_label_vote_counts_v2__* cache entries will expire within "
                "CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS"
            )
        )
