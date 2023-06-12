import datetime
import itertools
from typing import Any, Generator

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


def mark_archived_entries(
    read_mappings_generator: Generator[ReadFeedEntryUserMapping, None, None],
    batch_size=768,
):
    while True:
        batch = list(itertools.islice(read_mappings_generator, batch_size))
        if len(batch) < 1:
            break

        ReadFeedEntryUserMapping.objects.bulk_create(
            batch, batch_size=batch_size, ignore_conflicts=True
        )


def read_mapping_generator_fn(feed: Feed, user: User):
    grace_start = user.created_at + _USER_UNREAD_GRACE_INTERVAL

    feed_entries: QuerySet[FeedEntry]
    if (
        FeedEntry.objects.filter(feed=feed, published_at__gte=grace_start).count()
        > _USER_UNREAD_GRACE_MIN_COUNT
    ):
        feed_entries = FeedEntry.objects.filter(feed=feed, published_at__lt=grace_start)
    else:
        feed_entries = FeedEntry.objects.filter(feed=feed).order_by("published_at")[
            _USER_UNREAD_GRACE_MIN_COUNT:
        ]

    for feed_entry in feed_entries.iterator():
        yield ReadFeedEntryUserMapping(feed_entry=feed_entry, user=user)
