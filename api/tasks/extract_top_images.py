import logging
import traceback
from typing import Iterable

from django.db.models import F, Q
from stop_words import LANGUAGE_MAPPING as _STOP_WORDS_LANGUAGE_MAPPING

from api.models import FeedEntry
from api.top_image_extractor import TryAgain, extract_top_image_src, is_top_image_needed

_logger = logging.getLogger("rss_temple.tasks.extract_top_images")

STOP_WORDS_AVAILABLE_LANGUAGES: frozenset[str] = frozenset(
    _STOP_WORDS_LANGUAGE_MAPPING.keys()
)


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
        if (
            similar_feed_entry := FeedEntry.objects.exclude(uuid=feed_entry.uuid)
            .filter(url=feed_entry.url)
            .filter(
                Q(has_top_image_been_processed=True)
                | Q(
                    top_image_processing_attempt_count__gt=feed_entry.top_image_processing_attempt_count
                )
            )
            .order_by("-top_image_processing_attempt_count")
            .first()
        ):
            feed_entry.has_top_image_been_processed = (
                similar_feed_entry.has_top_image_been_processed
            )
            feed_entry.top_image_processing_attempt_count = (
                similar_feed_entry.top_image_processing_attempt_count
            )
            feed_entry.top_image_src = similar_feed_entry.top_image_src
            feed_entry.save(
                update_fields=(
                    "has_top_image_been_processed",
                    "top_image_processing_attempt_count",
                    "top_image_src",
                )
            )

            if feed_entry.has_top_image_been_processed:
                count += 1

                _logger.info("processed top image for %s", feed_entry.url)

            continue

        try:
            if is_top_image_needed(feed_entry.content):
                stop_words_language: str
                if feed_entry.language_id is not None:
                    if (
                        stop_words_language_ := feed_entry.language.iso639_1.lower()
                    ) in STOP_WORDS_AVAILABLE_LANGUAGES:
                        assert isinstance(stop_words_language_, str)
                        stop_words_language = stop_words_language_
                    else:
                        stop_words_language = ""
                else:
                    stop_words_language = ""

                feed_entry.top_image_src = (
                    extract_top_image_src(
                        feed_entry.url,
                        response_max_byte_count,
                        min_image_byte_count=min_image_byte_count,
                        min_image_width=min_image_width,
                        min_image_height=min_image_height,
                        stop_words_language=stop_words_language,
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

            _logger.info("processed top image for %s", feed_entry.url)
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
