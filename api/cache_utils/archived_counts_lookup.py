import uuid as uuid_
from typing import Any, Collection, Generator, NamedTuple

from django.conf import settings
from django.core.cache import BaseCache
from django.core.signals import setting_changed
from django.dispatch import receiver

from api.lock_context import lock_context
from api.models import Feed

_FEED_ARCHIVED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS: float | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _FEED_ARCHIVED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS

    _FEED_ARCHIVED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS = (
        settings.FEED_ARCHIVED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS
    )


_load_global_settings()


def _generate_cached_entries(
    feed_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> Generator[tuple[uuid_.UUID, int], None, None]:
    if not feed_uuids:
        return

    cache_entries: dict[str, int | None] = cache.get_many(
        f"archived_counts_lookup_{f_uuid}" for f_uuid in feed_uuids
    )

    for key, archived_count in cache_entries.items():
        if archived_count is not None:
            feed_uuid = uuid_.UUID(key.removeprefix(f"archived_counts_lookup_"))
            yield feed_uuid, archived_count


def save_archived_counts_lookup_to_cache(
    archived_counts_lookup: dict[uuid_.UUID, int],
    cache: BaseCache,
) -> None:
    cache.set_many(
        {
            f"archived_counts_lookup_{feed_uuid}": archived_count
            for feed_uuid, archived_count in archived_counts_lookup.items()
        },
        _FEED_ARCHIVED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS,
    )


class _GetArchivedCountsLookupFromCacheResult(NamedTuple):
    archived_counts_lookup: dict[uuid_.UUID, int]
    missing_feed_uuids: list[uuid_.UUID]


def get_archived_counts_lookup_from_cache(
    feed_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> _GetArchivedCountsLookupFromCacheResult:
    with lock_context(cache, f"archived_counts_lookup_lock"):
        archived_counts_lookup: dict[uuid_.UUID, int] = {
            feed_uuid: archived_count
            for feed_uuid, archived_count in _generate_cached_entries(feed_uuids, cache)
        }

        missing_feed_uuids = [
            f_uuid for f_uuid in feed_uuids if f_uuid not in archived_counts_lookup
        ]

        return _GetArchivedCountsLookupFromCacheResult(
            archived_counts_lookup, missing_feed_uuids
        )
