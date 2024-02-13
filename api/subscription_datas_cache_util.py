import uuid as uuid_
from typing import TypedDict

from django.core.cache import BaseCache

from api.models import SubscribedFeedUserMapping, User


class SubscriptionData(TypedDict):
    uuid: uuid_.UUID
    custom_title: str | None


def generate_subscription_datas(user: User, cache: BaseCache) -> list[SubscriptionData]:
    subscription_datas_cache_key = f"subscription_datas__{user.uuid}"
    subscription_datas: list[SubscriptionData] | None = cache.get(
        subscription_datas_cache_key
    )
    if subscription_datas is None:
        subscription_datas = [
            {
                "uuid": sfum.feed_id,
                "custom_title": sfum.custom_feed_title,
            }
            for sfum in SubscribedFeedUserMapping.objects.filter(user=user).iterator()
        ]
        cache.set(
            subscription_datas_cache_key,
            subscription_datas,
            None,
        )

    return subscription_datas
