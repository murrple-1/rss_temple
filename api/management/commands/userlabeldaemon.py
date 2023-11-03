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
    ClassifierLabelUserCalculated,
    SubscribedFeedUserMapping,
    User,
)

from ._daemoncommand import DaemonCommand


class Command(DaemonCommand):
    help = "Daemon to periodically calculate the labels of users"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("--top-x", type=int, default=10)
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
        ClassifierLabelUserCalculated.objects.filter(expires_at__lte=Now()).delete()

        # TODO setting
        expires_at = timezone.now() + datetime.timedelta(days=7)

        for user_uuid in User.objects.exclude(
            uuid__in=ClassifierLabelUserCalculated.objects.values("user_id")
        ).values_list("uuid", flat=True):
            counter = Counter(
                {
                    cl_dict["uuid"]: cl_dict["vote_count"]
                    for cl_dict in ClassifierLabel.objects.annotate(
                        vote_count=Coalesce(
                            Subquery(
                                ClassifierLabelFeedCalculated.objects.filter(
                                    feed_id__in=SubscribedFeedUserMapping.objects.filter(
                                        user_id=user_uuid
                                    ).values(
                                        "feed_id"
                                    ),
                                    classifier_label_id=OuterRef("uuid"),
                                )
                                .values("classifier_label_id")
                                .annotate(c=Count("uuid"))
                                .values("c")
                            ),
                            0,
                        )
                    ).values("uuid", "vote_count")
                }
            )

            ClassifierLabelUserCalculated.objects.bulk_create(
                ClassifierLabelUserCalculated(
                    classifier_label_id=classifier_label_uuid,
                    user_id=user_uuid,
                    expires_at=expires_at,
                )
                for classifier_label_uuid, _ in counter.most_common(top_x)
            )
