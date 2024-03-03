import uuid as uuid_
from typing import cast

from django.core.cache import BaseCache
from redis_lock.django_cache import RedisCache as RedisLockCache

from api.models import ReadFeedEntryUserMapping, User


def get_read_feed_entry_uuids_from_cache(
    user: User, cache: BaseCache
) -> tuple[list[uuid_.UUID], bool]:
    lock = (
        cache.lock(
            f"read_feed_entry_uuids_lock__{user.uuid}", expire=60, auto_renewal=True
        )
        if isinstance(cache, RedisLockCache)
        else None
    )
    if lock is not None:
        lock.acquire()

    try:
        cache_hit = True
        cache_key = f"read_feed_entry_uuids__{user.uuid}"
        read_feed_entry_uuids: list[uuid_.UUID] | None = cache.get(cache_key)
        if read_feed_entry_uuids is None:
            read_feed_entry_uuids = list(
                ReadFeedEntryUserMapping.objects.filter(user=user).values_list(
                    "feed_entry_id", flat=True
                )
            )
            cast(BaseCache, cache).set(
                cache_key,
                read_feed_entry_uuids,
                None,
            )
            cache_hit = False

        return read_feed_entry_uuids, cache_hit
    finally:
        if lock is not None:
            lock.release()


def delete_read_feed_entry_uuids_cache(user: User, cache: BaseCache) -> None:
    cache.delete(f"read_feed_entry_uuids__{user.uuid}")
