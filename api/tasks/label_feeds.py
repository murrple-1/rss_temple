import datetime
from collections import Counter

from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce, Now
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedCalculated,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
    Feed,
)


def label_feeds(top_x: int, expiry_interval: datetime.timedelta):
    ClassifierLabelFeedCalculated.objects.filter(expires_at__lte=Now()).delete()

    expires_at = timezone.now() + expiry_interval

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
