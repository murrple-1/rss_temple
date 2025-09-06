from typing import Any

import django

django.setup()

import datetime

import dramatiq
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.db.models.functions import Now
from django.utils import timezone
from requests.exceptions import RequestException

from api import content_type_util, rss_requests
from api.cache_utils.archived_counts_lookup import get_archived_counts_lookup_task
from api.cache_utils.counts_lookup import (
    _GetCountsLookupTaskResults_Lookup,
    get_counts_lookup_task,
)
from api.content_type_util import WrongContentTypeError
from api.feed_handler import FeedHandlerError
from api.models import (
    DuplicateFeedSuggestion,
    Feed,
    FeedEntry,
    SubscribedFeedUserMapping,
)
from api.requests_extensions import ResponseTooBig, safe_response_text
from api.tasks import archive_feed_entries as archive_feed_entries_
from api.tasks import extract_top_images as extract_top_images_
from api.tasks import feed_scrape as feed_scrape_
from api.tasks import find_duplicate_feeds as find_duplicate_feeds_
from api.tasks import label_feeds as label_feeds_
from api.tasks import label_users as label_users_
from api.tasks import purge_duplicate_feed_urls as purge_duplicate_feed_urls_
from api.tasks import purge_expired_data as purge_expired_data_
from api.tasks import setup_subscriptions as setup_subscriptions_
from api.tasks.feed_scrape import (
    error_update_backoff_until as feed_scrape__error_update_backoff_until,
)
from api.tasks.feed_scrape import (
    success_update_backoff_until as feed_scrape__success_update_backoff_until,
)
from api.tasks.setup_subscriptions import (
    get_first_entry as setup_subscriptions__get_first_entry,
)


@dramatiq.actor(queue_name="rss_temple", store_results=True)
def get_counts_lookup(
    user_uuid_str: str, feed_uuid_str: str, *args: Any, **kwargs: Any
) -> dict[str, _GetCountsLookupTaskResults_Lookup]:
    get_counts_lookup.logger.info("get_counts_lookup() started...")
    return get_counts_lookup_task(user_uuid_str, feed_uuid_str)


@dramatiq.actor(queue_name="rss_temple", store_results=True)
def get_archived_counts_lookup(
    feed_uuid_str: str, *args: Any, **kwargs: Any
) -> dict[str, int]:
    get_archived_counts_lookup.logger.info("get_archived_counts_lookup() started...")
    return get_archived_counts_lookup_task(feed_uuid_str)


@dramatiq.actor(queue_name="rss_temple")
def archive_feed_entries(*args: Any, limit=1000, **kwargs: Any) -> None:
    count = 0
    with transaction.atomic():
        for feed in Feed.objects.filter(
            archive_update_backoff_until__lte=Now()
        ).order_by("archive_update_backoff_until")[:limit]:
            count += 1

            archive_feed_entries_(
                feed,
                timezone.now(),
                settings.ARCHIVE_TIME_THRESHOLD,
                settings.ARCHIVE_COUNT_THRESHOLD,
                settings.ARCHIVE_BACKOFF_SECONDS,
            )

    archive_feed_entries.logger.info("processed %d feed(s) for archiving", count)


@dramatiq.actor(queue_name="rss_temple")
def purge_expired_data(*args: Any, **kwargs: Any) -> None:
    purge_expired_data_()
    purge_expired_data.logger.info("purged expired data")


@dramatiq.actor(queue_name="rss_temple")
def extract_top_images(
    response_max_byte_count: int,
    *args: Any,
    max_processing_attempts=3,
    min_image_byte_count=4500,
    min_image_width=250,
    min_image_height=250,
    db_limit=50,
    since: str | None = None,
    large_backlog_threshold=200,
    **kwargs: Any,
) -> None:
    since_ = (
        datetime.datetime.fromisoformat(since)
        if since is not None
        else datetime.datetime.min
    )
    if timezone.is_naive(since_):
        since_ = timezone.make_aware(since_)

    total_remaining = FeedEntry.objects.filter(
        has_top_image_been_processed=False
    ).count()
    if total_remaining > large_backlog_threshold:
        extract_top_images.logger.warning(
            "large extract-top-images backlog alert: %d is larger than threshold %d",
            total_remaining,
            large_backlog_threshold,
        )

    count = extract_top_images_(
        FeedEntry.objects.filter(has_top_image_been_processed=False)
        .filter(published_at__gte=since_)
        .order_by("-published_at")
        .select_related("language")[:db_limit],
        max_processing_attempts,
        min_image_byte_count,
        min_image_width,
        min_image_height,
        response_max_byte_count,
    )
    extract_top_images.logger.info("updated %d feed entry(s)", count)


@dramatiq.actor(queue_name="rss_temple")
def label_feeds(*args: Any, top_x=3, **kwargs: Any) -> None:
    label_feeds_(top_x, settings.LABELING_EXPIRY_INTERVAL)
    label_feeds.logger.info("feeds labelled")


@dramatiq.actor(queue_name="rss_temple")
def label_users(*args: Any, top_x=10, **kwargs: Any) -> None:
    label_users_(top_x, settings.LABELING_EXPIRY_INTERVAL)
    label_users.logger.info("users labelled")


@dramatiq.actor(queue_name="rss_temple")
def feed_scrape(
    response_max_byte_count: int,
    should_scrape_dead_feeds: bool,
    *args: Any,
    db_limit=1000,
    is_dead_max_interval_seconds: float | None = None,
    log_exception_traceback=False,
    **kwargs: Any,
) -> None:
    is_dead_max_interval = (
        datetime.timedelta(seconds=is_dead_max_interval_seconds)
        if is_dead_max_interval_seconds is not None
        else settings.FEED_IS_DEAD_MAX_INTERVAL
    )

    count = 0
    feed_urls_succeeded: list[str] = []

    with transaction.atomic():
        feed_q = Q(
            update_backoff_until__lte=Now(),
            db_updated_at__gte=Now() - is_dead_max_interval,
        )
        if not should_scrape_dead_feeds:
            feed_q &= Q(uuid__in=SubscribedFeedUserMapping.objects.values("feed_id"))

        for feed in (
            Feed.objects.select_for_update(skip_locked=True)
            .filter(feed_q)
            .order_by("update_backoff_until")[:db_limit]
            .iterator()
        ):
            count += 1

            try:
                response_text: str
                with rss_requests.get(feed.feed_url, stream=True) as response:
                    response.raise_for_status()

                    content_type = response.headers.get("Content-Type")
                    if content_type is not None and not content_type_util.is_feed(
                        content_type
                    ):
                        raise WrongContentTypeError(content_type)

                    response_text = safe_response_text(
                        response, response_max_byte_count
                    )

                feed_scrape_(feed, response_text)

                feed_urls_succeeded.append(feed.feed_url)

                feed.update_backoff_until = feed_scrape__success_update_backoff_until(
                    feed, settings.SUCCESS_BACKOFF_SECONDS
                )
                feed.consecutive_update_fail_count = 0
                feed.save(
                    update_fields=(
                        "db_updated_at",
                        "update_backoff_until",
                        "consecutive_update_fail_count",
                    )
                )
            except (
                RequestException,
                FeedHandlerError,
                ResponseTooBig,
                WrongContentTypeError,
            ) as e:
                if log_exception_traceback:
                    feed_scrape.logger.exception(
                        "failed to scrape feed '%s'", feed.feed_url
                    )
                else:
                    feed_scrape.logger.error(
                        "failed to scrape feed '%s' - %s",
                        feed.feed_url,
                        repr(e),
                    )

                Feed.objects.filter(uuid=feed.uuid).update(
                    update_backoff_until=feed_scrape__error_update_backoff_until(
                        feed,
                        settings.MIN_ERROR_BACKOFF_SECONDS,
                        settings.MAX_ERROR_BACKOFF_SECONDS,
                    ),
                    consecutive_update_fail_count=F("consecutive_update_fail_count")
                    + 1,
                )

    if feed_urls_succeeded:
        feed_scrape.logger.info(
            "attempted to scrape %d feed(s). successes: %s",
            count,
            ", ".join(f"'{fu}'" for fu in feed_urls_succeeded),
        )
    else:
        feed_scrape.logger.info("attempted to scrape %d feed(s)", count)


@dramatiq.actor(queue_name="rss_temple")
def setup_subscriptions(
    response_max_byte_count: int, *args: Any, **kwargs: Any
) -> None:
    feed_subscription_progress_entry = setup_subscriptions__get_first_entry()
    if feed_subscription_progress_entry is not None:
        setup_subscriptions_(feed_subscription_progress_entry, response_max_byte_count)
        setup_subscriptions.logger.info("subscription process entry(s) setup")
    else:
        setup_subscriptions.logger.info("no subscription process entry available")


@dramatiq.actor(queue_name="rss_temple")
def flag_duplicate_feeds(
    *args: Any,
    feed_count=1000,
    entry_compare_count=50,
    entry_intersection_threshold=5,
    **kwargs: Any,
) -> None:
    duplicate_feed_suggestions: list[DuplicateFeedSuggestion] = []

    for f1, f2 in find_duplicate_feeds_(
        feed_count, entry_compare_count, entry_intersection_threshold
    ):
        f1_id, f2_id = sorted([f1.uuid, f2.uuid], reverse=True)
        duplicate_feed_suggestions.append(
            DuplicateFeedSuggestion(feed1_id=f1_id, feed2_id=f2_id)
        )

    DuplicateFeedSuggestion.objects.bulk_create(
        duplicate_feed_suggestions, ignore_conflicts=True
    )

    flag_duplicate_feeds.logger.info(
        "%d possible duplicate(s) found: %s",
        len(duplicate_feed_suggestions),
        ", ".join(
            f"'{dfs.feed1.feed_url}'::'{dfs.feed2.feed_url}'"
            for dfs in duplicate_feed_suggestions
        ),
    )


@dramatiq.actor(queue_name="rss_temple")
def purge_duplicate_feed_urls(*args: Any, **kwargs: Any) -> None:
    purge_duplicate_feed_urls_()
    purge_duplicate_feed_urls.logger.info("purged duplicate feed URLs")
