import uuid as uuid_

from django.core.cache import BaseCache

from api.models import ReadFeedEntryUserMapping, User


def get_read_feed_entry_uuids_from_cache(
    user: User, cache: BaseCache
) -> tuple[list[uuid_.UUID], bool]:
    cache_hit = True
    cache_key = f"read_feed_entry_uuids__{user.uuid}"
    read_feed_entry_uuids: list[uuid_.UUID] | None = cache.get(cache_key)
    if read_feed_entry_uuids is None:
        read_feed_entry_uuids = list(
            ReadFeedEntryUserMapping.objects.filter(user=user).values_list(
                "feed_entry_id", flat=True
            )
        )
        cache.set(
            cache_key,
            read_feed_entry_uuids,
            None,
        )
        cache_hit = False

    return read_feed_entry_uuids, cache_hit


def delete_read_feed_entry_uuids_cache(user: User, cache: BaseCache) -> None:
    cache.delete(f"read_feed_entry_uuids__{user.uuid}")
