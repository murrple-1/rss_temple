import datetime
import uuid as uuid_
from collections import defaultdict
from itertools import batched

from django.db.models.functions import Now
from django.utils import timezone

from api.models import (
    ClassifierLabelFeedCalculated,
    ClassifierLabelUserCalculated,
    SubscribedFeedUserMapping,
)


def label_users(
    top_x: int, expiry_interval: datetime.timedelta, chunk_size: int = 500
) -> None:
    ClassifierLabelUserCalculated.objects.filter(expires_at__lte=Now()).delete()

    expires_at = timezone.now() + expiry_interval

    already_labelled = set(
        ClassifierLabelUserCalculated.objects.values_list("user_id", flat=True)
    )

    candidate_user_ids = (
        set(
            SubscribedFeedUserMapping.objects.filter(
                feed_id__in=ClassifierLabelFeedCalculated.objects.values("feed_id")
            )
            .values_list("user_id", flat=True)
            .distinct()
        )
        - already_labelled
    )

    for user_id_chunk in batched(sorted(candidate_user_ids), chunk_size):
        # feed -> users, for this chunk only
        feed_users: defaultdict[uuid_.UUID, list[uuid_.UUID]] = defaultdict(list)
        for mapping in (
            SubscribedFeedUserMapping.objects.filter(user_id__in=user_id_chunk)
            .values("user_id", "feed_id")
            .iterator()
        ):
            feed_users[mapping["feed_id"]].append(mapping["user_id"])

        scores: defaultdict[uuid_.UUID, defaultdict[uuid_.UUID, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        # NOTE: `feed_users.keys()` is the set of distinct feeds subscribed-to by
        # this chunk of up to `chunk_size` users, and is *not* itself bounded by
        # `chunk_size` -- a user with many subscriptions can push it arbitrarily
        # high. SQLite caps bound parameters at 32766 per statement, so this would
        # need restructuring (e.g. sub-chunking `feed_users.keys()` too) once any
        # user in a chunk has roughly 65+ subscriptions (chunk_size=500 users x
        # ~65 unique feeds each). Not reachable at this deployment's size; left
        # as-is rather than restructured pre-emptively.
        for row in (
            ClassifierLabelFeedCalculated.objects.filter(feed_id__in=feed_users.keys())
            .values("feed_id", "classifier_label_id", "weight")
            .iterator()
        ):
            for user_id in feed_users[row["feed_id"]]:
                scores[user_id][row["classifier_label_id"]] += float(row["weight"])

        ClassifierLabelUserCalculated.objects.bulk_create(
            ClassifierLabelUserCalculated(
                classifier_label_id=classifier_label_id,
                user_id=user_id,
                expires_at=expires_at,
                weight=score,
            )
            for user_id, label_scores in scores.items()
            for classifier_label_id, score in sorted(
                label_scores.items(), key=lambda t: t[1], reverse=True
            )[:top_x]
        )
