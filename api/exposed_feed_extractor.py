import logging
import pprint
from dataclasses import dataclass

import feedparser
import requests
from bs4 import BeautifulSoup

from api import rss_requests

_logger: logging.Logger | None = None


def logger() -> logging.Logger:  # pragma: no cover
    global _logger
    if _logger is None:
        _logger = logging.getLogger("rss_temple.exposed_feed_extractor")

    return _logger


@dataclass
class ExposedFeed:
    title: str
    href: str


def extract_exposed_feeds(
    url: str,
) -> list[ExposedFeed]:
    response: requests.Response
    try:
        response = rss_requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return []

    d = feedparser.parse(response.text, sanitize_html=False)

    if not d.get("bozo", True):
        logger().info(pprint.pformat(d))
        return [
            ExposedFeed(d.feed.get("title", url), url),
        ]

    # TODO investigate what errors this can throw (if any), and handle them
    soup = BeautifulSoup(response.text, "lxml")

    rss_links = soup.findAll("link", type="application/rss+xml")

    exposed_feeds: list[ExposedFeed] = []
    for rss_link in rss_links:
        href = rss_link.get("href")
        if not href:
            continue

        title = rss_link.get("title")
        if not title:
            title = href

        exposed_feeds.append(ExposedFeed(title, href))

    return exposed_feeds
