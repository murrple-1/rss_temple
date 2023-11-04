import datetime

from api.models import Feed, FeedEntry, ReadFeedEntryUserMapping


def archive_feed_entries(
    feed: Feed,
    now: datetime.datetime,
    archive_time_threshold: datetime.timedelta,
    archive_count_threshold: int,
    backoff_seconds: float,
) -> None:
    time_cutoff = now + archive_time_threshold

    count = 0
    newly_archived: list[FeedEntry] = []
    for feed_entry in feed.feed_entries.filter(is_archived=False).order_by(
        "-published_at", "-created_at", "-updated_at"
    ):
        count += 1
        if feed_entry.published_at < time_cutoff or count >= archive_count_threshold:
            feed_entry.is_archived = True
            newly_archived.append(feed_entry)

    FeedEntry.objects.bulk_update(newly_archived, ["is_archived"], batch_size=512)

    ReadFeedEntryUserMapping.objects.filter(feed_entry__in=newly_archived).delete()

    feed.archive_update_backoff_until = now + datetime.timedelta(
        seconds=backoff_seconds
    )
    feed.save(
        update_fields=[
            "archive_update_backoff_until",
        ]
    )
