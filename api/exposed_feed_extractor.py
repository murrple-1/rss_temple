import logging
import pprint
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup, ResultSet, Tag

from api import rss_requests
from api.requests_extensions import safe_response_text

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
    response_max_size=1000 * 1000,
    response_chunk_size=1000,
) -> list[ExposedFeed]:
    response_text: str
    try:
        response = rss_requests.get(url, stream=True)
        response.raise_for_status()
        response_text = safe_response_text(
            response, response_max_size, response_chunk_size
        )
    except requests.exceptions.RequestException:
        return []

    d = feedparser.parse(response_text, sanitize_html=False)

    if not d.get("bozo", True):
        logger().info(pprint.pformat(d))
        return [
            ExposedFeed(d.feed.get("title", url), url),
        ]

    # TODO investigate what errors this can throw (if any), and handle them
    soup = BeautifulSoup(response_text, "lxml")

    base_href: str | None = None
    if (
        isinstance((base_tag := soup.find("base")), Tag)
        and (base_href_ := base_tag.get("href"))
        and isinstance(base_href_, str)
    ):
        base_href = base_href_
    else:
        base_href = url

    rss_links: ResultSet[Tag] = soup.findAll(
        "link", rel="alternate", type="application/rss+xml"
    )

    exposed_feeds: list[ExposedFeed] = []
    for rss_link in rss_links:
        href = rss_link.get("href")
        if not href or not isinstance(href, str):
            continue

        href = urljoin(base_href, href)

        if (href_parse := urlparse(href)).scheme not in (
            "http",
            "https",
        ) or not href_parse.netloc:
            continue

        title = rss_link.get("title")
        if not title or not isinstance(title, str):
            title = href

        exposed_feeds.append(ExposedFeed(title, href))

    return exposed_feeds
