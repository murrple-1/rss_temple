import datetime
import logging
import pprint
import time

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
    d = feedparser.parse(text, sanitize_html=False)

    logger().info("feed info: %s", pprint.pformat(d))

    if "bozo" in d and d.bozo == 1:
        raise FeedHandlerError from d.bozo_exception

    return d


def d_feed_2_feed(d_feed, url: str):
    feed = Feed(
        feed_url=url, title=d_feed.get("title", url), home_url=d_feed.get("link")
    )

    if "published_parsed" in d_feed:
        time_tuple = d_feed.published_parsed

        feed.published_at = _parsed_time_tuple_to_datetime(time_tuple)
    else:
        # field auto-filled by DB
        pass

    if "updated_parsed" in d_feed:
        time_tuple = d_feed.updated_parsed

        feed.updated_at = _parsed_time_tuple_to_datetime(time_tuple)
    else:
        feed.updated_at = None

    return feed


def d_entry_2_feed_entry(d_entry):
    feed_entry = FeedEntry(id=d_entry.get("id"))

    if "created_parsed" in d_entry:
        time_tuple = d_entry.created_parsed

        if time_tuple is not None:
            feed_entry.created_at = _parsed_time_tuple_to_datetime(time_tuple)
        else:  # pragma: no cover
            feed_entry.created_at = None
    else:
        feed_entry.created_at = None

    if "published_parsed" in d_entry:
        time_tuple = d_entry.published_parsed

        if time_tuple is not None:
            feed_entry.published_at = _parsed_time_tuple_to_datetime(time_tuple)
        else:  # pragma: no cover
            # field auto-filled by DB
            pass
    else:
        # field auto-filled by DB
        pass

    if "updated_parsed" in d_entry:
        time_tuple = d_entry.updated_parsed

        if time_tuple is not None:
            feed_entry.updated_at = _parsed_time_tuple_to_datetime(time_tuple)
        else:  # pragma: no cover
            feed_entry.updated_at = None
    else:
        feed_entry.updated_at = None

    title = d_entry.get("title")
    if title is None:
        raise ValueError("title not set")

    feed_entry.title = title

    url = d_entry.get("link")
    if url is None:
        raise ValueError("url not set")

    if not validators.url(url):
        raise ValueError("url malformed")

    feed_entry.url = url

    content: str | None = None

    if content is None:
        if "content" in d_entry:
            d_entry_content = next(
                (
                    dec
                    for dec in d_entry.content
                    if dec.type in {"text/html", "application/xhtml+xml", "text/plain"}
                ),
                None,
            )
            if d_entry_content is not None:
                content = content_sanitize.sanitize(d_entry_content.value)

    if content is None:
        if "summary" in d_entry:
            content = content_sanitize.sanitize(d_entry.summary)

    if content is None:
        raise ValueError("content not set")

    feed_entry.content = content

    feed_entry.author_name = d_entry.get("author")

    return feed_entry


def d_feed_2_feed_tags(d_feed):
    d_feed_tags = d_feed.get("tags", [])

    feed_tags = frozenset(d_feed_tag.term for d_feed_tag in d_feed_tags)

    return feed_tags


def d_entry_2_entry_tags(d_entry):
    d_entry_tags = d_entry.get("tags", [])

    entry_tags = frozenset(d_entry_tag.term for d_entry_tag in d_entry_tags)

    return entry_tags


def _parsed_time_tuple_to_datetime(t: time.struct_time):
    return datetime.datetime.fromtimestamp(time.mktime(t), datetime.timezone.utc)
