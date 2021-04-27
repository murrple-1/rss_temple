import itertools

from django.conf import settings
from django.dispatch import receiver
from django.core.signals import setting_changed

from api import models


_USER_UNREAD_GRACE_INTERVAL = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _USER_UNREAD_GRACE_INTERVAL

    _USER_UNREAD_GRACE_INTERVAL = settings.USER_UNREAD_GRACE_INTERVAL


_load_global_settings()


def mark_archived_entries(read_mappings_generator, batch_size=1000):
    while True:
        batch = list(itertools.islice(read_mappings_generator, batch_size))
        if len(batch) < 1:
            break

        models.ReadFeedEntryUserMapping.objects.bulk_create(batch, batch_size=batch_size, ignore_conflicts=True)


def read_mapping_generator_fn(feed, user):
    for feed_entry in models.FeedEntry.objects.filter(feed=feed, published_at__lt=(user.created_at + _USER_UNREAD_GRACE_INTERVAL)).iterator():
        yield models.ReadFeedEntryUserMapping(feed_entry=feed_entry, user=user)
