import io
import logging
import pprint
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser
from bs4 import BeautifulSoup, ResultSet, Tag
from requests.exceptions import ConnectionError, HTTPError, Timeout

from api import content_type_util, rss_requests
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
    response_max_byte_count: int,
) -> list[ExposedFeed]:
    response_text: str
    content_type: str | None
    try:
        with rss_requests.get(url, stream=True) as response:
            response.raise_for_status()

            content_type = response.headers.get("Content-Type")

            if (
                content_type is None
                or content_type_util.is_feed(content_type)
                or content_type_util.is_html(content_type)
            ):
                response_text = safe_response_text(response, response_max_byte_count)
            else:
                return []
    except (Timeout, ConnectionError, HTTPError):
        logger().exception(f"unable to download '{url}'")
        return []

    if content_type is None or content_type_util.is_feed(content_type):
        d: Any
        # TODO this is a hack until https://github.com/kurtmckee/feedparser/issues/427 is resolved...then `io.StringIO` should be used
        with io.BytesIO(response_text.encode()) as f:
            d = feedparser.parse(f, sanitize_html=False)

        if not d.get("bozo", True):
            logger().info(pprint.pformat(d))
            return [
                ExposedFeed(d.feed.get("title", url), url),
            ]

    if content_type is None or content_type_util.is_html(content_type):
        soup: BeautifulSoup
        try:
            soup = BeautifulSoup(response_text, "lxml")
        except Exception:  # pragma: no cover
            logger().exception("unknown BeautifulSoup error")
            return []

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

    raise RuntimeError("shouldn't be possible")  # pragma: no cover
