import datetime
import io
import logging
import pprint
import time
from typing import Any

import feedparser
import validators

from api import content_sanitize
from api.models import Feed, FeedEntry

_logger: logging.Logger | None = None


class FeedHandlerError(Exception):
    pass


def logger() -> logging.Logger:  # pragma: no cover
    global _logger
    if _logger is None:
        _logger = logging.getLogger("rss_temple.feed_handler")

    return _logger


def text_2_d(text: str):
    d: Any
    # TODO this is a hack until https://github.com/kurtmckee/feedparser/issues/427 is resolved...then `io.StringIO` should be used
    with io.BytesIO(text.encode()) as f:
        d = feedparser.parse(f, sanitize_html=False)

    logger().info("feed info: %s", pprint.pformat(d))

    if d.get("bozo", True):
        raise FeedHandlerError from d.bozo_exception

    return d


def d_feed_2_feed(d_feed, url: str, now: datetime.datetime):
    feed = Feed(
        feed_url=url, title=d_feed.get("title", url), home_url=d_feed.get("link")
    )

    if time_tuple := d_feed.get("published_parsed"):
        if (dt := _parsed_time_tuple_to_datetime(time_tuple)) <= now:
            feed.published_at = dt
        else:
            # field auto-filled by DB
            pass
    else:
        # field auto-filled by DB
        pass

    if time_tuple := d_feed.get("updated_parsed"):
        if (dt := _parsed_time_tuple_to_datetime(time_tuple)) <= now:
            feed.updated_at = dt
        else:  # pragma: no cover
            feed.updated_at = None
    else:
        feed.updated_at = None

    return feed


def d_entry_2_feed_entry(d_entry, now: datetime.datetime):
    feed_entry = FeedEntry(
        id=d_entry.get("id"),
        author_name=d_entry.get("author"),
        title=_d_entry_to_title(d_entry),
        url=_d_entry_to_url(d_entry),
        content=_d_entry_to_content(d_entry),
    )

    if time_tuple := d_entry.get("created_parsed"):
        if (dt := _parsed_time_tuple_to_datetime(time_tuple)) <= now:
            feed_entry.created_at = dt
        else:  # pragma: no cover
            feed_entry.created_at = None
    else:
        feed_entry.created_at = None

    if time_tuple := d_entry.get("published_parsed"):
        if (dt := _parsed_time_tuple_to_datetime(time_tuple)) <= now:
            feed_entry.published_at = dt
    else:
        # field auto-filled by DB
        pass

    if time_tuple := d_entry.get("updated_parsed"):
        if (dt := _parsed_time_tuple_to_datetime(time_tuple)) <= now:
            feed_entry.updated_at = dt
        else:  # pragma: no cover
            feed_entry.updated_at = None
    else:
        feed_entry.updated_at = None

    return feed_entry


def _parsed_time_tuple_to_datetime(t: time.struct_time):
    return datetime.datetime.fromtimestamp(time.mktime(t), datetime.timezone.utc)


def _d_entry_to_title(d_entry) -> str | None:
    title: str | None = d_entry.get("title")
    if title is None:
        raise ValueError("title not set")

    return title


def _d_entry_to_url(d_entry) -> str:
    url: str | None = d_entry.get("link")

    if url is None:
        if enclosures := d_entry.get("enclosures", []):
            # TODO if there are multiple enclosures, should they be ranked in some way?
            url = enclosures[0].get("href")

    if url is None:
        raise ValueError("url not set")

    if not validators.url(url):
        raise ValueError("url malformed")

    return url


def _d_entry_to_content(d_entry) -> str:
    content: str | None = None

    if content is None:
        if content_list := d_entry.get("content"):
            d_entry_content = next(
                (
                    dec
                    for dec in content_list
                    if dec.type in {"text/html", "application/xhtml+xml", "text/plain"}
                ),
                None,
            )
            if d_entry_content is not None:
                content = content_sanitize.sanitize(d_entry_content.value)

    if content is None:
        if summary := d_entry.get("summary"):
            content = content_sanitize.sanitize(summary)

    if content is None:
        raise ValueError("content not set")

    return content
