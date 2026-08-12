import datetime
import uuid as uuid_
from collections import defaultdict
from itertools import batched

from django.db.models import Count, Sum
from django.db.models.functions import Now
from django.utils import timezone

from api.models import (
    ClassifierLabelFeedCalculated,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
)


def label_feeds(
    top_x: int, expiry_interval: datetime.timedelta, chunk_size: int = 500
) -> None:
    ClassifierLabelFeedCalculated.objects.filter(expires_at__lte=Now()).delete()

    expires_at = timezone.now() + expiry_interval

    already_labelled = set(
        ClassifierLabelFeedCalculated.objects.values_list("feed_id", flat=True)
    )

    candidate_feed_ids = (
        set(
            ClassifierLabelFeedEntryVote.objects.values_list(
                "feed_entry__feed_id", flat=True
            ).distinct()
        )
        | set(
            ClassifierLabelFeedEntryCalculated.objects.values_list(
                "feed_entry__feed_id", flat=True
            ).distinct()
        )
    ) - already_labelled

    for feed_id_chunk in batched(sorted(candidate_feed_ids), chunk_size):
        scores: defaultdict[uuid_.UUID, defaultdict[uuid_.UUID, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        for row in (
            ClassifierLabelFeedEntryVote.objects.filter(
                feed_entry__feed_id__in=feed_id_chunk
            )
            .values("feed_entry__feed_id", "classifier_label_id")
            .annotate(score=Count("uuid"))
            .iterator()
        ):
            scores[row["feed_entry__feed_id"]][row["classifier_label_id"]] += float(
                row["score"]
            )

        for row in (
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry__feed_id__in=feed_id_chunk
            )
            .values("feed_entry__feed_id", "classifier_label_id")
            .annotate(score=Sum("weight"))
            .iterator()
        ):
            scores[row["feed_entry__feed_id"]][row["classifier_label_id"]] += float(
                row["score"] or 0.0
            )

        ClassifierLabelFeedCalculated.objects.bulk_create(
            ClassifierLabelFeedCalculated(
                classifier_label_id=classifier_label_id,
                feed_id=feed_id,
                expires_at=expires_at,
                weight=score,
            )
            for feed_id, label_scores in scores.items()
            for classifier_label_id, score in sorted(
                label_scores.items(), key=lambda t: t[1], reverse=True
            )[:top_x]
        )
