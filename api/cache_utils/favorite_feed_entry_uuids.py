import uuid as uuid_

from django.core.cache import BaseCache

from api.models import User


def get_favorite_feed_entry_uuids_from_cache(
    user: User, cache: BaseCache
) -> tuple[list[uuid_.UUID], bool]:
    cache_hit = True
    cache_key = f"favorite_feed_entry_uuids__{user.uuid}"
    favorite_feed_entry_uuids: list[uuid_.UUID] | None = cache.get(cache_key)
    if favorite_feed_entry_uuids is None:
        favorite_feed_entry_uuids = list(
            User.favorite_feed_entries.through.objects.filter(user=user).values_list(
                "feedentry_id", flat=True
            )
        )
        cache.set(
            cache_key,
            favorite_feed_entry_uuids,
            None,
        )
        cache_hit = False

    return favorite_feed_entry_uuids, cache_hit


def delete_favorite_feed_entry_uuids_cache(user: User, cache: BaseCache) -> None:
    cache.delete(f"favorite_feed_entry_uuids__{user.uuid}")
