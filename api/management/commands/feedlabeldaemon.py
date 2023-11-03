import datetime
from collections import Counter
from typing import Any

from django.core.management.base import CommandError, CommandParser
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce, Now
from django.db.utils import OperationalError
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedCalculated,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
    Feed,
)

from ._daemoncommand import DaemonCommand


class Command(DaemonCommand):
    help = "Daemon to periodically calculate the labels of feeds"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("--top-x", type=int, default=3)
        parser.add_argument(
            "--sleep-seconds", type=float, default=60.0 * 60.0 * 24.0
        )  # 24 hours
        parser.add_argument("--single-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        top_x: int = options["top_x"]

        if options["single_run"]:
            self._label_loop(top_x)
        else:
            exit = self._setup_exit_event()

            try:
                while not exit.is_set():
                    self._label_loop(top_x)

                    exit.wait(options["sleep_seconds"])
            except OperationalError as e:
                raise CommandError("db went away") from e
            except Exception as e:
                raise CommandError("loop stopped unexpectedly") from e

    def _label_loop(self, top_x: int) -> None:
        ClassifierLabelFeedCalculated.objects.filter(expires_at__lte=Now()).delete()

        # TODO setting
        expires_at = timezone.now() + datetime.timedelta(days=7)

        for feed_uuid in Feed.objects.exclude(
            uuid__in=ClassifierLabelFeedCalculated.objects.values("feed_id")
        ).values_list("uuid", flat=True):
            counter = Counter(
                {
                    cl_dict["uuid"]: cl_dict["overall_vote_count"]
                    for cl_dict in ClassifierLabel.objects.annotate(
                        overall_vote_count=Coalesce(
                            Subquery(
                                ClassifierLabelFeedEntryVote.objects.filter(
                                    feed_entry__feed_id=feed_uuid,
                                    classifier_label_id=OuterRef("uuid"),
                                )
                                .values("feed_entry__feed")
                                .annotate(c1=Count("uuid"))
                                .values("c1")
                            ),
                            0,
                        )
                        + Coalesce(
                            Subquery(
                                ClassifierLabelFeedEntryCalculated.objects.filter(
                                    feed_entry__feed_id=feed_uuid,
                                    classifier_label_id=OuterRef("uuid"),
                                )
                                .values("feed_entry__feed")
                                .annotate(c2=Count("uuid"))
                                .values("c2")
                            ),
                            0,
                        )
                    ).values("uuid", "overall_vote_count")
                }
            )

            ClassifierLabelFeedCalculated.objects.bulk_create(
                ClassifierLabelFeedCalculated(
                    classifier_label_id=classifier_label_uuid,
                    feed_id=feed_uuid,
                    expires_at=expires_at,
                )
                for classifier_label_uuid, _ in counter.most_common(top_x)
            )
