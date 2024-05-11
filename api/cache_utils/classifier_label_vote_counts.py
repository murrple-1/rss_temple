import uuid as uuid_
from collections import defaultdict
from typing import Any, Collection, Generator

from django.conf import settings
from django.core.cache import BaseCache
from django.core.signals import setting_changed
from django.db import connection
from django.dispatch import receiver

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
    FeedEntry,
)

_CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS: float | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS

    _CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS = (
        settings.CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS
    )


_load_global_settings()


def _generate_cached_entries(
    feed_entry_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> Generator[tuple[uuid_.UUID, dict[uuid_.UUID, int]], None, None]:
    if not feed_entry_uuids:
        return

    cache_entries: dict[str, dict[uuid_.UUID, int] | None] = cache.get_many(
        f"classifier_label_vote_counts__{fe_uuid}" for fe_uuid in feed_entry_uuids
    )

    for key, entry in cache_entries.items():
        if entry is not None:
            feed_entry_uuid = uuid_.UUID(
                key.removeprefix("classifier_label_vote_counts__")
            )
            yield feed_entry_uuid, entry


def get_classifier_label_vote_counts_from_cache(
    feed_entry_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> tuple[dict[uuid_.UUID, dict[uuid_.UUID, int]], bool]:
    feed_entry_uuids = frozenset(feed_entry_uuids)

    classifier_label_vote_counts: dict[uuid_.UUID, dict[uuid_.UUID, int]] = {
        feed_entry_uuid: entry
        for feed_entry_uuid, entry in _generate_cached_entries(feed_entry_uuids, cache)
    }
    cache_hit = True

    missing_feed_entry_uuids = feed_entry_uuids.difference(
        classifier_label_vote_counts.keys()
    )
    if missing_feed_entry_uuids:
        placeholders = ", ".join("%s" for _ in missing_feed_entry_uuids)
        params: tuple[Any, ...]
        if connection.vendor == "sqlite":
            params = tuple(str(u).replace("-", "") for u in missing_feed_entry_uuids)
        else:
            params = tuple(missing_feed_entry_uuids)

        # There isn't a foreign-key between ClassifierLabel's and FeedEntry's,
        # so this is the only way to write this as a single query within Django that I've found
        rows = ClassifierLabel.objects.raw(
            f"""
            SELECT
            t1."uuid" AS "uuid",
            t2."uuid" AS "feed_entry_uuid",
            (
                (
                    SELECT
                        COUNT(*)
                    FROM
                        {ClassifierLabelFeedEntryVote._meta.db_table} AS u1
                    WHERE
                        u1."classifier_label_id" = t1."uuid"
                        AND u1."feed_entry_id" = t2."uuid"
                ) + (
                    SELECT
                        COUNT(*)
                    FROM
                        {ClassifierLabelFeedEntryCalculated._meta.db_table} AS u2
                    WHERE
                        u2."classifier_label_id" = t1."uuid"
                        AND u2."feed_entry_id" = t2."uuid"
                )
            ) AS "vote_count"
            FROM
                {ClassifierLabel._meta.db_table} AS t1
                JOIN {FeedEntry._meta.db_table} AS t2 ON TRUE
            WHERE
                t2."uuid" IN ({placeholders})
            GROUP BY
                t1."uuid",
                t2."uuid"
        """,
            params,
        )

        missing_classifier_label_vote_counts: dict[
            uuid_.UUID, dict[uuid_.UUID, int]
        ] = defaultdict(dict)
        for row in rows:
            feed_entry_uuid = row.feed_entry_uuid
            if not isinstance(feed_entry_uuid, uuid_.UUID):
                feed_entry_uuid = uuid_.UUID(feed_entry_uuid)

            missing_classifier_label_vote_counts[feed_entry_uuid][
                row.uuid
            ] = row.vote_count

        classifier_label_vote_counts.update(missing_classifier_label_vote_counts)

        cache.set_many(
            {
                f"classifier_label_vote_counts__{feed_entry_uuid}": vote_counts
                for feed_entry_uuid, vote_counts in missing_classifier_label_vote_counts.items()
            },
            _CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS,
        )
        cache_hit = False

    return classifier_label_vote_counts, cache_hit
