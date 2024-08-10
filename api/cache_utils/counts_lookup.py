import uuid as uuid_
from typing import Any, Collection, Generator, NamedTuple, TypedDict

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


def save_counts_lookup_to_cache(
    user: User,
    counts_lookup: dict[uuid_.UUID, Feed._CountsDescriptor],
    cache: BaseCache,
) -> None:
    cache.set_many(
        {
            f"counts_lookup_{user.uuid}_{feed_uuid}": (
                counts_descriptor.unread_count,
                counts_descriptor.read_count,
            )
            for feed_uuid, counts_descriptor in counts_lookup.items()
        },
        _FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS,
    )


class _GetCountsLookupFromCacheResults(NamedTuple):
    counts_lookup: dict[uuid_.UUID, Feed._CountsDescriptor]
    missing_feed_uuids: list[uuid_.UUID]


def get_counts_lookup_from_cache(
    user: User, feed_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> _GetCountsLookupFromCacheResults:
    with lock_context(cache, f"counts_lookup_lock__{user.uuid}"):
        counts_lookup: dict[uuid_.UUID, Feed._CountsDescriptor] = {
            feed_uuid: Feed._CountsDescriptor(unread, read)
            for feed_uuid, unread, read in _generate_cached_entries(
                user, feed_uuids, cache
            )
        }

        missing_feed_uuids = [
            f_uuid for f_uuid in feed_uuids if f_uuid not in counts_lookup
        ]

        return _GetCountsLookupFromCacheResults(counts_lookup, missing_feed_uuids)


def increment_read_in_counts_lookup_cache(
    user: User, feed_increments: dict[uuid_.UUID, int], cache: BaseCache
) -> None:
    with lock_context(cache, f"counts_lookup_lock__{user.uuid}"):
        counts_lookup: dict[uuid_.UUID, Feed._CountsDescriptor] = {}
        for feed_uuid, unread, read in _generate_cached_entries(
            user, feed_increments.keys(), cache
        ):
            incr = feed_increments[feed_uuid]
            counts_lookup[feed_uuid] = Feed._CountsDescriptor(
                max(0, unread - incr), max(0, read + incr)
            )

        save_counts_lookup_to_cache(user, counts_lookup, cache)


class _GetCountsLookupTaskResults_Lookup(TypedDict):
    unread_count: int
    read_count: int


def get_counts_lookup_task(
    user_uuid_str: str, feed_uuid_str: str
) -> dict[str, _GetCountsLookupTaskResults_Lookup]:
    user = User.objects.get(uuid=uuid_.UUID(user_uuid_str))
    counts_lookup = Feed.generate_counts_lookup(user, [uuid_.UUID(feed_uuid_str)])

    return {
        str(u): {
            "unread_count": l.unread_count,
            "read_count": l.read_count,
        }
        for u, l in counts_lookup.items()
    }
