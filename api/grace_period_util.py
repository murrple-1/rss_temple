import datetime
from typing import Any

from django.conf import settings
from django.core.signals import setting_changed
from django.db.models import QuerySet
from django.dispatch import receiver

from api.models import Feed, FeedEntry, ReadFeedEntryUserMapping, User

_USER_UNREAD_GRACE_INTERVAL: datetime.timedelta
_USER_UNREAD_GRACE_MIN_COUNT: int


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _USER_UNREAD_GRACE_INTERVAL
    global _USER_UNREAD_GRACE_MIN_COUNT

    _USER_UNREAD_GRACE_INTERVAL = settings.USER_UNREAD_GRACE_INTERVAL
    _USER_UNREAD_GRACE_MIN_COUNT = settings.USER_UNREAD_GRACE_MIN_COUNT


_load_global_settings()


def generate_grace_period_read_entries(
    feed: Feed,
    user: User,
):
    grace_start = user.created_at + _USER_UNREAD_GRACE_INTERVAL

    feed_entries_qs: QuerySet[FeedEntry]
    if (
        FeedEntry.objects.filter(
            feed=feed, published_at__gte=grace_start, is_archived=False
        ).count()
        > _USER_UNREAD_GRACE_MIN_COUNT
    ):
        feed_entries_qs = FeedEntry.objects.filter(
            feed=feed, published_at__lt=grace_start
        )
    else:
        feed_entries_qs = FeedEntry.objects.filter(
            feed=feed, is_archived=False
        ).order_by("published_at")[_USER_UNREAD_GRACE_MIN_COUNT:]

    return [
        ReadFeedEntryUserMapping(feed_entry=feed_entry, user=user)
        for feed_entry in feed_entries_qs
    ]
