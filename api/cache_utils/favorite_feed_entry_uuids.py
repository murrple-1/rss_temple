import uuid as uuid_
from typing import NamedTuple

from django.core.cache import BaseCache

from api.lock_context import lock_context
from api.models import User


class _GetFavoriteFeedEntryUuidsFromCacheResults(NamedTuple):
    favorite_feed_entry_uuids: list[uuid_.UUID]
    cache_hit: bool


def get_favorite_feed_entry_uuids_from_cache(
    user: User, cache: BaseCache
) -> _GetFavoriteFeedEntryUuidsFromCacheResults:
    with lock_context(cache, f"favorite_feed_entry_uuids_lock__{user.uuid}"):
        cache_hit = True
        cache_key = f"favorite_feed_entry_uuids__{user.uuid}"
        favorite_feed_entry_uuids: list[uuid_.UUID] | None = cache.get(cache_key)
        if favorite_feed_entry_uuids is None:
            favorite_feed_entry_uuids = list(
                User.favorite_feed_entries.through.objects.filter(
                    user=user
                ).values_list("feedentry_id", flat=True)
            )
            cache.set(
                cache_key,
                favorite_feed_entry_uuids,
                None,
            )
            cache_hit = False

        return _GetFavoriteFeedEntryUuidsFromCacheResults(
            favorite_feed_entry_uuids, cache_hit
        )


def delete_favorite_feed_entry_uuids_cache(user: User, cache: BaseCache) -> None:
    cache.delete(f"favorite_feed_entry_uuids__{user.uuid}")
