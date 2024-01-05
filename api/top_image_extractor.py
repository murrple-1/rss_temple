import io
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from PIL import Image, UnidentifiedImageError
from requests import Response
from requests.exceptions import HTTPError, Timeout

from api import rss_requests
from api.requests_extensions import (
    ResponseTooBig,
    safe_response_content,
    safe_response_text,
)


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
    response: Response
    try:
        response = rss_requests.get(url, stream=True)
    except Timeout as e:  # pragma: no cover
        raise TryAgain from e

    try:
        response.raise_for_status()
    except HTTPError as e:
        if response.status_code in (404,):
            return None
        else:  # pragma: no cover
            raise TryAgain from e

    response_text: str
    try:
        response_text = safe_response_text(response, response_max_byte_count)
    except ResponseTooBig as e:  # pragma: no cover
        raise TryAgain from e

    # TODO investigate what errors this can throw (if any), and handle them
    soup = BeautifulSoup(response_text, "lxml")

    og_image = soup.find("meta", property="og:image")

    if not isinstance(og_image, Tag):
        return None

    og_image_src = og_image.get("content")
    if not isinstance(og_image_src, str):
        return None

    og_image_src = urljoin(url, og_image_src)

    content_length: int | None = None

    image_head_r: Response | None
    try:
        image_head_r = rss_requests.head(og_image_src)
    except Timeout:  # pragma: no cover
        # if HEAD fails, just continue on to GET
        image_head_r = None

    if image_head_r is not None:  # pragma: no cover
        try:
            image_head_r.raise_for_status()
        except HTTPError:
            image_head_r = None

    if image_head_r is not None:  # pragma: no cover
        content_length_str = image_head_r.headers.get("content-length")
        if content_length_str is not None:
            try:
                content_length = int(content_length_str)
            except ValueError:
                pass

    if content_length is not None:  # pragma: no cover
        if content_length < min_image_byte_count:
            return None

    image_r: Response
    try:
        image_r = rss_requests.get(og_image_src, stream=True)
    except Timeout as e:  # pragma: no cover
        raise TryAgain from e

    try:
        image_r.raise_for_status()
    except HTTPError as e:
        if image_r.status_code in (404,):
            return None
        else:  # pragma: no cover
            raise TryAgain from e

    content: bytes
    try:
        content = safe_response_content(image_r, response_max_byte_count)
    except ResponseTooBig as e:  # pragma: no cover
        raise TryAgain from e

    if content_length is None:
        content_length = len(content)
        if content_length < min_image_byte_count:
            return None

    try:
        with io.BytesIO(content) as f:
            with Image.open(f) as image:
                if image.width < min_image_width or image.height < min_image_height:
                    return None
    except UnidentifiedImageError:
        return None

    return og_image_src
