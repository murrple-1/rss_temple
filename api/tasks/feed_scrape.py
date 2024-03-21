import datetime

from django.db.models import Q
from django.utils import timezone

from api import feed_handler
from api.models import Feed, FeedEntry
from api.text_classifier.lang_detector import detect_iso639_3
from api.text_classifier.prep_content import prep_for_lang_detection


def feed_scrape(feed: Feed, response_text: str):
    d = feed_handler.text_2_d(response_text)

    new_feed_entries: list[FeedEntry] = []

    now = timezone.now()

    for d_entry in d.get("entries", []):
        feed_entry: FeedEntry
        try:
            feed_entry = feed_handler.d_entry_2_feed_entry(d_entry, now)
        except ValueError:  # pragma: no cover
            continue

        old_feed_entry: FeedEntry | None
        old_feed_entry_get_q = Q(feed=feed)

        if feed_entry.id is not None:
            old_feed_entry_get_q &= Q(id=feed_entry.id)
        else:
            old_feed_entry_get_q &= Q(url=feed_entry.url)

        if feed_entry.updated_at is None:
            old_feed_entry_get_q &= Q(updated_at__isnull=True)
        else:
            old_feed_entry_get_q &= Q(updated_at=feed_entry.updated_at)

        try:
            old_feed_entry = FeedEntry.objects.get(old_feed_entry_get_q)
        except FeedEntry.DoesNotExist:
            old_feed_entry = None

        if old_feed_entry is not None:
            old_feed_entry.id = feed_entry.id
            old_feed_entry.content = feed_entry.content
            old_feed_entry.author_name = feed_entry.author_name
            old_feed_entry.created_at = feed_entry.created_at
            old_feed_entry.updated_at = feed_entry.updated_at
            old_feed_entry.language_id = detect_iso639_3(
                prep_for_lang_detection(feed_entry.title, feed_entry.content)
            )

            old_feed_entry.save(
                update_fields=[
                    "id",
                    "content",
                    "author_name",
                    "created_at",
                    "updated_at",
                    "language_id",
                ]
            )
        else:
            feed_entry.feed = feed

            feed_entry.language_id = detect_iso639_3(
                prep_for_lang_detection(feed_entry.title, feed_entry.content)
            )

            new_feed_entries.append(feed_entry)

    FeedEntry.objects.bulk_create(new_feed_entries, ignore_conflicts=True)

    feed.db_updated_at = now


def success_update_backoff_until(
    feed: Feed, success_backoff_seconds: float
) -> datetime.datetime:
    assert feed.db_updated_at is not None
    return feed.db_updated_at + datetime.timedelta(seconds=success_backoff_seconds)


def error_update_backoff_until(
    feed: Feed, min_error_backoff_seconds: float, max_error_backoff_seconds: float
) -> datetime.datetime:
    last_written_at = feed.db_updated_at or feed.db_created_at

    backoff_delta_seconds: float = (
        feed.update_backoff_until - last_written_at
    ).total_seconds()

    if backoff_delta_seconds < min_error_backoff_seconds:
        backoff_delta_seconds = min_error_backoff_seconds
    elif backoff_delta_seconds > max_error_backoff_seconds:
        backoff_delta_seconds += max_error_backoff_seconds
    else:
        backoff_delta_seconds *= 2.0

    return last_written_at + datetime.timedelta(seconds=backoff_delta_seconds)
