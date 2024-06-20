import uuid as uuid_
from typing import Any, Collection, Generator

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


def _save_entries_to_cache(
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


def get_archived_counts_lookup_from_cache(
    feed_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> tuple[dict[uuid_.UUID, int], bool]:
    with lock_context(cache, f"archived_counts_lookup_lock"):
        cache_hit = True
        archived_counts_lookup: dict[uuid_.UUID, int] = {
            feed_uuid: archived_count
            for feed_uuid, archived_count in _generate_cached_entries(feed_uuids, cache)
        }

        missing_feed_uuids = [
            f_uuid for f_uuid in feed_uuids if f_uuid not in archived_counts_lookup
        ]

        if missing_feed_uuids:
            missing_archived_counts_lookup = Feed.generate_archived_counts_lookup(
                missing_feed_uuids
            )
            archived_counts_lookup.update(missing_archived_counts_lookup)

            _save_entries_to_cache(missing_archived_counts_lookup, cache)

            cache_hit = False

        return archived_counts_lookup, cache_hit
