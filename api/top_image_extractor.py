import io
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from PIL import Image, UnidentifiedImageError
from requests import Response
from requests.exceptions import HTTPError, ReadTimeout

from api import rss_requests


class TryAgain(Exception):
    pass


def is_top_image_needed(content: str) -> bool:
    soup = BeautifulSoup(content, "lxml")
    return len(soup.findAll("img")) < 1


def extract_top_image_src(
    url: str,
    min_image_byte_count=4500,
    min_image_width=256,
    min_image_height=256,
) -> str | None:
    # TODO Currently, the top image is just the OpenGraph image (if it exists).
    # However, in the future, this might be expanded to do some `goose3`-like
    # smart-parsing of the webpage
    r: Response
    try:
        r = rss_requests.get(url)
    except ReadTimeout as e:
        raise TryAgain from e

    try:
        r.raise_for_status()
    except HTTPError as e:
        if r.status_code == 404:
            return None
        else:
            raise TryAgain from e

    soup = BeautifulSoup(r.content, "lxml")

    og_image = soup.find("meta", property="og:image")

    if not isinstance(og_image, Tag):
        return None

    og_image_src = og_image.get("content")
    if not isinstance(og_image_src, str):
        return None

    og_image_src = urljoin(url, og_image_src)

    # TODO do a HEAD request first, to check the byte count

    image_r: Response
    try:
        image_r = rss_requests.get(og_image_src)
    except ReadTimeout as e:
        raise TryAgain from e

    try:
        image_r.raise_for_status()
    except HTTPError as e:
        if image_r.status_code == 404:
            return None
        else:
            raise TryAgain from e

    content = image_r.content
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
