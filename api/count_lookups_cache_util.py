import uuid as uuid_
from typing import Any, Collection

from django.conf import settings
from django.core.cache import BaseCache
from django.core.signals import setting_changed
from django.dispatch import receiver

from api.models import Feed, User

_FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS: float | None


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS

    _FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS = (
        settings.FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS
    )


_load_global_settings()


def get_count_lookups_from_cache(
    user: User, feed_uuids: Collection[uuid_.UUID], cache: BaseCache
) -> dict[uuid_.UUID, Feed._CountsDescriptor]:
    cache_entries: dict[str, tuple[int, int] | None] = cache.get_many(
        [f"counts_lookup_{user.uuid}_{f_uuid}" for f_uuid in feed_uuids]
    )

    count_lookups: dict[uuid_.UUID, Feed._CountsDescriptor] = {}
    for key, entry in cache_entries.items():
        if entry is not None:
            unread, read = entry
            feed_uuid = uuid_.UUID(key.removeprefix(f"counts_lookup_{user.uuid}_"))
            count_lookups[feed_uuid] = Feed._CountsDescriptor(unread, read)

    missing_feed_uuids = [
        f_uuid for f_uuid in feed_uuids if f_uuid not in count_lookups
    ]

    if missing_feed_uuids:
        missing_count_lookups = Feed.generate_counts_lookup(user, missing_feed_uuids)
        count_lookups.update(missing_count_lookups)

        cache.set_many(
            {
                f"counts_lookup_{user.uuid}_{feed_uuid}": (
                    count_lookup.unread_count,
                    count_lookup.read_count,
                )
                for feed_uuid, count_lookup in missing_count_lookups.items()
            },
            _FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS,
        )

    return count_lookups


def increment_read_in_count_lookups_cache(
    user: User, feed_increments: dict[uuid_.UUID, int], cache: BaseCache
) -> None:
    cache_entries: dict[str, tuple[int, int] | None] = cache.get_many(
        [f"counts_lookup_{user.uuid}_{k_uuid}" for k_uuid in feed_increments.keys()]
    )

    count_lookups: dict[uuid_.UUID, Feed._CountsDescriptor] = {}
    for key, entry in cache_entries.items():
        if entry is not None:
            unread, read = entry
            feed_uuid = uuid_.UUID(key.removeprefix(f"counts_lookup_{user.uuid}_"))

            incr = feed_increments[feed_uuid]
            count_lookups[feed_uuid] = Feed._CountsDescriptor(
                unread - incr, read + incr
            )

    missing_feed_uuids = [
        k_uuid for k_uuid in feed_increments.keys() if k_uuid not in count_lookups
    ]

    if missing_feed_uuids:
        count_lookups.update(Feed.generate_counts_lookup(user, missing_feed_uuids))

    cache.set_many(
        {
            f"counts_lookup_{user.uuid}_{feed_uuid}": (
                count_lookup.unread_count,
                count_lookup.read_count,
            )
            for feed_uuid, count_lookup in count_lookups.items()
        },
        _FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS,
    )
