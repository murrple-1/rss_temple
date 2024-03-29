import logging
import traceback
from typing import Iterable

from django.db.models import F

from api.models import FeedEntry
from api.top_image_extractor import TryAgain, extract_top_image_src, is_top_image_needed

_logger = logging.getLogger("rss_temple")


def extract_top_images(
    feed_entry_queryset: Iterable[FeedEntry],
    max_processing_attempts: int,
    min_image_byte_count: int,
    min_image_width: int,
    min_image_height: int,
    response_max_byte_count: int,
) -> int:
    count = 0
    for feed_entry in feed_entry_queryset:
        try:
            if is_top_image_needed(feed_entry.content):
                feed_entry.top_image_src = (
                    extract_top_image_src(
                        feed_entry.url,
                        response_max_byte_count,
                        min_image_byte_count=min_image_byte_count,
                        min_image_width=min_image_width,
                        min_image_height=min_image_height,
                    )
                    or ""
                )
            else:
                feed_entry.top_image_src = ""

            feed_entry.has_top_image_been_processed = True
            feed_entry.save(
                update_fields=("has_top_image_been_processed", "top_image_src")
            )

            count += 1
        except TryAgain:  # pragma: no cover
            if feed_entry.top_image_processing_attempt_count < max_processing_attempts:
                FeedEntry.objects.filter(uuid=feed_entry.uuid).update(
                    top_image_processing_attempt_count=F(
                        "top_image_processing_attempt_count"
                    )
                    + 1
                )
                _logger.debug(
                    "feed entry '%s' transient error. try again later\n%s",
                    feed_entry.url,
                    traceback.format_exc(),
                )
            else:
                FeedEntry.objects.filter(uuid=feed_entry.uuid).update(
                    top_image_src="", has_top_image_been_processed=True
                )
                count += 1

                _logger.debug(
                    "feed entry '%s' transient error. no more attempts\n%s",
                    feed_entry.url,
                    traceback.format_exc(),
                )
        except Exception:  # pragma: no cover
            _logger.debug(
                "failed to find top image for '%s'\n%s",
                feed_entry.url,
                traceback.format_exc(),
            )
    return count
