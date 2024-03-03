import uuid as uuid_
from typing import Any, Collection

from django.conf import settings
from django.core.cache import BaseCache
from django.core.signals import setting_changed
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.dispatch import receiver

from api.lock_context import lock_context
from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
)

_CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS: float | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS

    _CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS = (
        settings.CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS
    )


_load_global_settings()


def get_classifier_label_vote_counts_from_cache(
    feed_entry_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> tuple[dict[uuid_.UUID, dict[uuid_.UUID, int]], bool]:
    classifier_label_vote_counts: dict[uuid_.UUID, dict[uuid_.UUID, int]] = {}
    cache_hit = True

    for feed_entry_uuid in feed_entry_uuids:
        with lock_context(
            cache, f"classifier_label_vote_counts_lock__{feed_entry_uuid}"
        ):
            cache_key = f"classifier_label_vote_counts__{feed_entry_uuid}"
            vote_counts: dict[uuid_.UUID, int] | None = cache.get(cache_key)

            if vote_counts is None:
                vote_counts = {
                    d["uuid"]: d["vote_count"]
                    for d in ClassifierLabel.objects.annotate(
                        vote_count=Coalesce(
                            Subquery(
                                ClassifierLabelFeedEntryVote.objects.filter(
                                    feed_entry_id=feed_entry_uuid,
                                    classifier_label_id=OuterRef("uuid"),
                                )
                                .values("feed_entry")
                                .annotate(c1=Count("uuid"))
                                .values("c1")
                            ),
                            0,
                        )
                        + Coalesce(
                            Subquery(
                                ClassifierLabelFeedEntryCalculated.objects.filter(
                                    feed_entry_id=feed_entry_uuid,
                                    classifier_label_id=OuterRef("uuid"),
                                )
                                .values("feed_entry")
                                .annotate(c2=Count("uuid"))
                                .values("c2")
                            ),
                            0,
                        ),
                    ).values("uuid", "vote_count")
                }

                cache.set(
                    cache_key,
                    vote_counts,
                    _CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS,
                )
                cache_hit = False

        classifier_label_vote_counts[feed_entry_uuid] = vote_counts

    return classifier_label_vote_counts, cache_hit
