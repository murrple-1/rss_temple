import datetime
from collections import Counter

from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce, Now
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedCalculated,
    ClassifierLabelUserCalculated,
    SubscribedFeedUserMapping,
    User,
)


def label_users(top_x: int, expiry_interval: datetime.timedelta):
    ClassifierLabelUserCalculated.objects.filter(expires_at__lte=Now()).delete()

    expires_at = timezone.now() + expiry_interval

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
                                ).values("feed_id"),
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
