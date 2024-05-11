import uuid as uuid_
from typing import Any, Collection, Generator

from django.conf import settings
from django.core.cache import BaseCache
from django.core.signals import setting_changed
from django.dispatch import receiver

from api.lock_context import lock_context
from api.models import Feed, User

_FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS: float | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS

    _FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS = (
        settings.FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS
    )


_load_global_settings()


def _generate_cached_entries(
    user: User, feed_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> Generator[tuple[uuid_.UUID, int, int], None, None]:
    if not feed_uuids:
        return

    cache_entries: dict[str, tuple[int, int] | None] = cache.get_many(
        f"counts_lookup_{user.uuid}_{f_uuid}" for f_uuid in feed_uuids
    )

    for key, entry in cache_entries.items():
        if entry is not None:
            unread, read = entry
            feed_uuid = uuid_.UUID(key.removeprefix(f"counts_lookup_{user.uuid}_"))
            yield feed_uuid, unread, read


def _save_entries_to_cache(
    user: User,
    counts_lookup: dict[uuid_.UUID, Feed._CountsDescriptor],
    cache: BaseCache,
) -> None:
    cache.set_many(
        {
            f"counts_lookup_{user.uuid}_{feed_uuid}": (
                count_lookup.unread_count,
                count_lookup.read_count,
            )
            for feed_uuid, count_lookup in counts_lookup.items()
        },
        _FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS,
    )


def get_count_lookups_from_cache(
    user: User, feed_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> tuple[dict[uuid_.UUID, Feed._CountsDescriptor], bool]:
    with lock_context(cache, f"count_lookup_lock__{user.uuid}"):
        cache_hit = True
        count_lookups: dict[uuid_.UUID, Feed._CountsDescriptor] = {
            feed_uuid: Feed._CountsDescriptor(unread, read)
            for feed_uuid, unread, read in _generate_cached_entries(
                user, feed_uuids, cache
            )
        }

        missing_feed_uuids = [
            f_uuid for f_uuid in feed_uuids if f_uuid not in count_lookups
        ]

        if missing_feed_uuids:
            missing_count_lookups = Feed.generate_counts_lookup(
                user, missing_feed_uuids
            )
            count_lookups.update(missing_count_lookups)

            _save_entries_to_cache(user, missing_count_lookups, cache)

            cache_hit = False

        return count_lookups, cache_hit


def increment_read_in_count_lookups_cache(
    user: User, feed_increments: dict[uuid_.UUID, int], cache: BaseCache
) -> None:
    with lock_context(cache, f"count_lookup_lock__{user.uuid}"):
        count_lookups: dict[uuid_.UUID, Feed._CountsDescriptor] = {}
        for feed_uuid, unread, read in _generate_cached_entries(
            user, feed_increments.keys(), cache
        ):
            incr = feed_increments[feed_uuid]
            count_lookups[feed_uuid] = Feed._CountsDescriptor(
                max(0, unread - incr), max(0, read + incr)
            )

        missing_feed_uuids = [
            k_uuid for k_uuid in feed_increments.keys() if k_uuid not in count_lookups
        ]

        if missing_feed_uuids:
            count_lookups.update(Feed.generate_counts_lookup(user, missing_feed_uuids))

        _save_entries_to_cache(user, count_lookups, cache)
