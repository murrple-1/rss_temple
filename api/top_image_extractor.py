import io
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from PIL import Image, UnidentifiedImageError
from requests.exceptions import HTTPError, Timeout

from api import content_type_util, rss_requests
from api.requests_extensions import (
    ResponseTooBig,
    safe_response_content,
    safe_response_text,
)

_logger: logging.Logger | None = None


def logger() -> logging.Logger:  # pragma: no cover
    global _logger
    if _logger is None:
        _logger = logging.getLogger("rss_temple.top_image_extractor")

    return _logger


class TryAgain(Exception):
    pass


def is_top_image_needed(content: str) -> bool:
    soup = BeautifulSoup(content, "lxml")
    return len(soup.findAll("img")) < 1


def extract_top_image_src(
    url: str,
    response_max_byte_count: int,
    min_image_byte_count=4500,
    min_image_width=256,
    min_image_height=256,
) -> str | None:
    # TODO Currently, the top image is just the OpenGraph image (if it exists).
    # However, in the future, this might be expanded to do some `goose3`-like
    # smart-parsing of the webpage
    response_text: str
    try:
        with rss_requests.get(url, stream=True) as response:
            try:
                response.raise_for_status()
            except HTTPError as e:
                if response.status_code in (404,):
                    return None
                else:  # pragma: no cover
                    raise TryAgain from e

            content_type = response.headers.get("Content-Type")
            if content_type is None or not content_type_util.is_html(content_type):
                return None

            try:
                response_text = safe_response_text(response, response_max_byte_count)
            except ResponseTooBig as e:  # pragma: no cover
                raise TryAgain from e
    except Timeout as e:  # pragma: no cover
        raise TryAgain from e

    soup: BeautifulSoup
    try:
        soup = BeautifulSoup(response_text, "lxml")
    except Exception as e:  # pragma: no cover
        logger().exception("unknown BeautifulSoup error")
        raise TryAgain from e

    og_image = soup.find("meta", property="og:image")

    if not isinstance(og_image, Tag):
        return None

    og_image_src = og_image.get("content")
    if not isinstance(og_image_src, str):
        return None

    og_image_src = urljoin(url, og_image_src)

    content: bytes
    try:
        with rss_requests.get(og_image_src, stream=True) as image_response:
            try:
                image_response.raise_for_status()
            except HTTPError as e:
                if image_response.status_code in (404,):
                    return None
                else:  # pragma: no cover
                    raise TryAgain from e
            try:
                content = safe_response_content(image_response, response_max_byte_count)
            except ResponseTooBig as e:  # pragma: no cover
                raise TryAgain from e
    except Timeout as e:  # pragma: no cover
        raise TryAgain from e

    if len(content) < min_image_byte_count:
        return None

    try:
        with io.BytesIO(content) as f:
            with Image.open(f) as image:
                if image.width < min_image_width or image.height < min_image_height:
                    return None
    except UnidentifiedImageError:
        return None

    return og_image_src
