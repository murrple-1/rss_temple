import datetime
import pprint
import logging

import feedparser

import requests

from api import models
from api.exceptions import QueryException

_logger = None
def logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger('rss_temple')

    return _logger

def url_2_d(url):
    response = None
    try:
        response = requests.get(url, headers={
            'User-Agent': 'RSS Temple',
        })
    except requests.exceptions.RequestException:
        raise QueryException('feed not found', 404)

    d = feedparser.parse(response.text)

    logger().info('feed info: %s', pprint.pformat(d))

    if 'bozo' in d and d.bozo == 1:
        raise QueryException('feed malformed', 401)

    return d

def d_feed_2_feed(d_feed, url):
    feed = models.Feed()
    feed.feed_url = url

    feed.title = d_feed.get('title')
    feed.home_url = d_feed.get('link')

    if 'published_parsed' in d_feed:
        time_tuple = d_feed.published_parsed

        feed.published_at = __time_tuple_to_datetime(time_tuple)
    else:
        # field auto-filled by DB
        pass

    if 'updated_parsed' in d_feed:
        time_tuple = d_feed.updated_parsed

        feed.updated_at = __time_tuple_to_datetime(time_tuple)
    else:
        feed.updated_at = None

    return feed


def d_entry_2_feed_entry(d_entry):
    feed_entry = models.FeedEntry()

    feed_entry.id = d_entry.get('id')

    if 'created_parsed' in d_entry:
        time_tuple = d_entry.created_parsed

        feed_entry.created_at = __time_tuple_to_datetime(time_tuple)
    else:
        feed_entry.created_at = None

    if 'published_parsed' in d_entry:
        time_tuple = d_entry.published_parsed

        feed_entry.published_at = __time_tuple_to_datetime(time_tuple)
    else:
        # field auto-filled by DB
        pass

    if 'updated_parsed' in d_entry:
        time_tuple = d_entry.updated_parsed

        feed_entry.updated_at = __time_tuple_to_datetime(time_tuple)
    else:
        feed_entry.updated_at = None

    feed_entry.title = d_entry.get('title')

    feed_entry.url = d_entry.get('link')

    if 'content' in d_entry:
        content = None

        content_dicts = d_entry.content

        for content_dict in content_dicts:
            if content_dict.type in ['text/html', 'application/xhtml+xml']:
                # prioritize these types
                content = content_dict.value
                break
            elif content_dict.type in ['text/plain']:
                # these types are fine too
                content = content_dict.value

        feed_entry.content = content
    else:
        feed_entry.content = None

    feed_entry.author_name = d_entry.get('author')

    return feed_entry


def d_feed_2_feed_tags(d_feed):
    d_feed_tags = d_feed.get('tags', [])

    feed_tags = frozenset(d_feed_tag.term for d_feed_tag in d_feed_tags)

    return feed_tags


def d_entry_2_entry_tags(d_entry):
    d_entry_tags = d_entry.get('tags', [])

    entry_tags = frozenset(d_entry_tag.term for d_entry_tag in d_entry_tags)

    return entry_tags


def __time_tuple_to_datetime(t):
    return datetime.datetime(t[0], t[1], t[2], t[3], t[4], t[5])
