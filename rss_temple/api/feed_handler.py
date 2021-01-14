import datetime
import pprint
import logging

import feedparser

from html_sanitizer import Sanitizer

from api import models
from api.exceptions import QueryException

_sanitizer = Sanitizer()

_logger = None


def logger():  # pragma: no cover
    global _logger
    if _logger is None:
        _logger = logging.getLogger('rss_temple')

    return _logger


def text_2_d(text):
    d = feedparser.parse(text)

    logger().info('feed info: %s', pprint.pformat(d))

    if 'bozo' in d and d.bozo == 1:
        raise QueryException('feed malformed', 401)

    return d


def d_feed_2_feed(d_feed, url):
    feed = models.Feed(
        feed_url=url, title=d_feed.get('title', url), home_url=d_feed.get('link'))

    if 'published_parsed' in d_feed:
        time_tuple = d_feed.published_parsed

        feed.published_at = _time_tuple_to_datetime(time_tuple)
    else:
        # field auto-filled by DB
        pass

    if 'updated_parsed' in d_feed:
        time_tuple = d_feed.updated_parsed

        feed.updated_at = _time_tuple_to_datetime(time_tuple)
    else:
        feed.updated_at = None

    return feed


def d_entry_2_feed_entry(d_entry):
    feed_entry = models.FeedEntry(id=d_entry.get('id'))

    if 'created_parsed' in d_entry:
        time_tuple = d_entry.created_parsed

        feed_entry.created_at = _time_tuple_to_datetime(time_tuple)
    else:
        feed_entry.created_at = None

    if 'published_parsed' in d_entry:
        time_tuple = d_entry.published_parsed

        feed_entry.published_at = _time_tuple_to_datetime(time_tuple)
    else:
        # field auto-filled by DB
        pass

    if 'updated_parsed' in d_entry:
        time_tuple = d_entry.updated_parsed

        feed_entry.updated_at = _time_tuple_to_datetime(time_tuple)
    else:
        feed_entry.updated_at = None

    feed_entry.title = d_entry.get('title')

    feed_entry.url = d_entry.get('link')

    content = None
    if 'summary' in d_entry:
        content = d_entry.summary

    if type(content) is str:
        content = _sanitizer.sanitize(content)

    feed_entry.content = content

    feed_entry.author_name = d_entry.get('author')

    feed_entry.hash = feed_entry.entry_hash()

    return feed_entry


def d_feed_2_feed_tags(d_feed):
    d_feed_tags = d_feed.get('tags', [])

    feed_tags = frozenset(d_feed_tag.term for d_feed_tag in d_feed_tags)

    return feed_tags


def d_entry_2_entry_tags(d_entry):
    d_entry_tags = d_entry.get('tags', [])

    entry_tags = frozenset(d_entry_tag.term for d_entry_tag in d_entry_tags)

    return entry_tags


def _time_tuple_to_datetime(t):
    return datetime.datetime(t[0], t[1], t[2], t[3], t[4], t[5])
