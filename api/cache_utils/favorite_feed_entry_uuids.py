import uuid as uuid_
from typing import cast

from django.core.cache import BaseCache
from redis_lock.django_cache import RedisCache as RedisLockCache

from api.models import User


def get_favorite_feed_entry_uuids_from_cache(
    user: User, cache: BaseCache
) -> tuple[list[uuid_.UUID], bool]:
    lock = (
        cache.lock(
            f"favorite_feed_entry_uuids_lock__{user.uuid}", expire=60, auto_renewal=True
        )
        if isinstance(cache, RedisLockCache)
        else None
    )
    if lock is not None:
        lock.acquire()

    try:
        cache_hit = True
        cache_key = f"favorite_feed_entry_uuids__{user.uuid}"
        favorite_feed_entry_uuids: list[uuid_.UUID] | None = cache.get(cache_key)
        if favorite_feed_entry_uuids is None:
            favorite_feed_entry_uuids = list(
                User.favorite_feed_entries.through.objects.filter(
                    user=user
                ).values_list("feedentry_id", flat=True)
            )
            cast(BaseCache, cache).set(
                cache_key,
                favorite_feed_entry_uuids,
                None,
            )
            cache_hit = False

        return favorite_feed_entry_uuids, cache_hit
    finally:
        if lock is not None:
            lock.release()


def delete_favorite_feed_entry_uuids_cache(user: User, cache: BaseCache) -> None:
    cache.delete(f"favorite_feed_entry_uuids__{user.uuid}")
