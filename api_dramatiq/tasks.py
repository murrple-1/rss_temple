import django

django.setup()

import datetime

import dramatiq
from django.conf import settings
from django.db import transaction
from django.db.models.functions import Now
from django.utils import timezone
from requests.exceptions import HTTPError

from api import content_type_util, rss_requests
from api.content_type_util import WrongContentTypeError
from api.feed_handler import FeedHandlerError
from api.models import Feed, FeedEntry
from api.requests_extensions import ResponseTooBig, safe_response_text
from api.tasks import archive_feed_entries as archive_feed_entries_
from api.tasks import extract_top_images as extract_top_images_
from api.tasks import feed_scrape as feed_scrape_
from api.tasks import label_feeds as label_feeds_
from api.tasks import label_users as label_users_
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
from api_dramatiq.broker import broker
from api_dramatiq.encoder import UJSONEncoder

dramatiq.set_broker(broker)
dramatiq.set_encoder(UJSONEncoder())


@dramatiq.actor(queue_name="rss_temple")
def archive_feed_entries(limit=1000) -> None:
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

    archive_feed_entries.logger.info("updated %d feed archives this round", count)


@dramatiq.actor(queue_name="rss_temple")
def purge_expired_data() -> None:
    purge_expired_data_()


@dramatiq.actor(queue_name="rss_temple")
def extract_top_images(
    response_max_byte_count: int,
    max_processing_attempts=3,
    min_image_byte_count=4500,
    min_image_width=250,
    min_image_height=250,
    db_limit=50,
    since: str | None = None,
) -> None:
    since_ = (
        datetime.datetime.fromisoformat(since)
        if since is not None
        else datetime.datetime.min
    )
    if timezone.is_naive(since_):
        since_ = timezone.make_aware(since_)
    count = extract_top_images_(
        FeedEntry.objects.filter(has_top_image_been_processed=False)
        .filter(published_at__gte=since_)
        .order_by("-published_at")[:db_limit],
        max_processing_attempts,
        min_image_byte_count,
        min_image_width,
        min_image_height,
        response_max_byte_count,
    )
    extract_top_images.logger.info("updated %d", count)


@dramatiq.actor(queue_name="rss_temple")
def label_feeds(top_x=3) -> None:
    label_feeds_(top_x, settings.LABELING_EXPIRY_INTERVAL)


@dramatiq.actor(queue_name="rss_temple")
def label_users(top_x=10) -> None:
    label_users_(top_x, settings.LABELING_EXPIRY_INTERVAL)


@dramatiq.actor(queue_name="rss_temple")
def feed_scrape(response_max_byte_count: int, db_limit=1000) -> None:
    count = 0
    with transaction.atomic():
        for feed in (
            Feed.objects.select_for_update(skip_locked=True)
            .filter(update_backoff_until__lte=Now())
            .order_by("update_backoff_until")[:db_limit]
        ):
            count += 1

            try:
                response = rss_requests.get(feed.feed_url, stream=True)
                response.raise_for_status()

                content_type = response.headers.get("Content-Type")
                if content_type is None or not content_type_util.is_feed(content_type):
                    raise WrongContentTypeError(content_type)

                response_text = safe_response_text(response, response_max_byte_count)

                feed_scrape_(feed, response_text)

                feed_scrape.logger.info("scrapped '%s'", feed.feed_url)

                feed.update_backoff_until = feed_scrape__success_update_backoff_until(
                    feed, settings.SUCCESS_BACKOFF_SECONDS
                )
                feed.save(
                    update_fields=[
                        "db_updated_at",
                        "update_backoff_until",
                    ]
                )
            except (
                HTTPError,
                FeedHandlerError,
                ResponseTooBig,
                UnicodeDecodeError,
                WrongContentTypeError,
            ):
                feed_scrape.logger.exception("failed to scrap feed '%s'", feed.feed_url)

                feed.update_backoff_until = feed_scrape__error_update_backoff_until(
                    feed,
                    settings.MIN_ERROR_BACKOFF_SECONDS,
                    settings.MAX_ERROR_BACKOFF_SECONDS,
                )
                feed.save(update_fields=["update_backoff_until"])

    feed_scrape.logger.info("scrapped %d feeds this round", count)


@dramatiq.actor(queue_name="rss_temple")
def setup_subscriptions(
    response_max_byte_count: int,
) -> None:
    feed_subscription_progress_entry = setup_subscriptions__get_first_entry()
    if feed_subscription_progress_entry is not None:
        setup_subscriptions.logger.info("starting subscription processing...")
        setup_subscriptions_(feed_subscription_progress_entry, response_max_byte_count)
    else:
        setup_subscriptions.logger.info("no subscription process entry available")
