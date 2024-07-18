import uuid as uuid_
from typing import NamedTuple, TypedDict

from django.core.cache import BaseCache

from api.lock_context import lock_context
from api.models import SubscribedFeedUserMapping, User


class SubscriptionData(TypedDict):
    uuid: uuid_.UUID
    custom_title: str | None


class _GetSubscriptionDatasFromCacheResults(NamedTuple):
    subscription_datas: list[SubscriptionData]
    cache_hit: bool


def get_subscription_datas_from_cache(
    user: User, cache: BaseCache
) -> _GetSubscriptionDatasFromCacheResults:
    with lock_context(cache, f"subscription_datas_lock__{user.uuid}"):
        cache_hit = True
        cache_key = f"subscription_datas__{user.uuid}"
        subscription_datas: list[SubscriptionData] | None = cache.get(cache_key)
        if subscription_datas is None:
            subscription_datas = [
                {
                    "uuid": sfum.feed_id,
                    "custom_title": sfum.custom_feed_title,
                }
                for sfum in SubscribedFeedUserMapping.objects.filter(
                    user=user
                ).iterator()
            ]
            cache.set(
                cache_key,
                subscription_datas,
                None,
            )
            cache_hit = False

        return _GetSubscriptionDatasFromCacheResults(subscription_datas, cache_hit)


def delete_subscription_data_cache(user: User, cache: BaseCache) -> None:
    cache.delete(f"subscription_datas__{user.uuid}")
