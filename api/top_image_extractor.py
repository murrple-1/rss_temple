import io
import logging
from typing import NamedTuple
from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup, NavigableString, PageElement, Tag
from PIL import Image, UnidentifiedImageError
from requests.exceptions import HTTPError, RequestException

from api import content_type_util, rss_requests
from api.requests_extensions import (
    ResponseTooBig,
    safe_response_content,
    safe_response_text,
)

_logger = logging.getLogger("rss_temple.top_image_extractor")


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
    except RequestException as e:  # pragma: no cover
        raise TryAgain from e

    soup: BeautifulSoup
    try:
        soup = BeautifulSoup(response_text, "lxml")
    except Exception as e:  # pragma: no cover
        _logger.exception("unknown BeautifulSoup error")
        raise TryAgain from e

    og_image = soup.find("meta", property="og:image")

    if not isinstance(og_image, Tag):
        return None

    og_image_src = og_image.get("content")
    if not isinstance(og_image_src, str):
        return None

    og_image_src = urljoin(url, og_image_src)

    image_content: bytes
    try:
        with rss_requests.get(og_image_src, stream=True) as image_response:
            try:
                image_response.raise_for_status()
            except HTTPError as e:
                if image_response.status_code in (404,):
                    return None
                else:  # pragma: no cover
                    raise TryAgain from e

            content_type = image_response.headers.get("Content-Type")
            if content_type is None or not content_type_util.is_image(content_type):
                return None

            content_length_str = image_response.headers.get("Content-Length")
            if content_length_str is not None:
                try:
                    if int(content_length_str) < min_image_byte_count:
                        return None
                except ValueError:  # pragma: no cover
                    pass

            try:
                image_content = safe_response_content(
                    image_response, response_max_byte_count
                )
            except ResponseTooBig as e:  # pragma: no cover
                raise TryAgain from e
    except RequestException as e:  # pragma: no cover
        raise TryAgain from e

    if len(image_content) < min_image_byte_count:
        return None  # pragma: no cover

    try:
        with io.BytesIO(image_content) as f:
            with Image.open(f) as image:
                if image.width < min_image_width or image.height < min_image_height:
                    return None
    except UnidentifiedImageError:
        return None

    return og_image_src


# TODO experimental code below

_BAD_PATTERN = re.compile(
    r"(?:ad|ads|advert|sponsor|banner|logo|icon|sprite|avatar|promo|header|footer|nav|tracking|pixel|placeholder|spacer|blank|doubleclick|googlesyndication)",
    re.IGNORECASE,
)
# Common ad/tracker domains
_BAD_DOMAINS: list[str] = [
    "doubleclick.net",
    "googlesyndication.com",
    "adservice.google.com",
    "adnxs.com",
    "criteo.com",
    "adsystem.com",
]


def _is_bad_url(url: str) -> bool:
    parse_result = urlparse(url)
    return any(bad in parse_result.netloc for bad in _BAD_DOMAINS)


def _is_bad_filename(filename: str) -> bool:
    return _BAD_PATTERN.search(filename) is not None


def _is_bad_class_id(img_tag: Tag) -> bool:
    for attr in ["class", "id"]:
        vals = img_tag.get(attr, [])
        if isinstance(vals, str):
            vals = [vals]

        if any(_BAD_PATTERN.search(str(v)) for v in vals):
            return True

    return False


_BAD_ALT_TERMS = re.compile(
    r"(?:logo|icon|avatar|banner|decorative|advertisement|promo|spacer|placeholder)",
    re.IGNORECASE,
)


def _is_probably_decorative(
    img_tag: Tag, src_url: str, page_title_keywords: frozenset[str]
) -> bool:
    """Combined heuristics for decorative/ad images."""
    filename = src_url.split("/")[-1].lower()

    if _is_bad_class_id(img_tag) or _is_bad_url(src_url) or _is_bad_filename(filename):
        return True

    alt = img_tag.get("alt", "")
    assert isinstance(alt, str)
    alt = alt.strip()
    if alt:
        if _BAD_ALT_TERMS.search(alt):
            return True

        if page_title_keywords and not any(kw in alt for kw in page_title_keywords):
            return True

    # Check for data URIs or blank src
    if src_url.startswith("data:") or not src_url:
        return True

    return False


_GOOD_CLASS = re.compile(r"(?:content|article|post|entry)", re.IGNORECASE)
_BAD_CLASS = re.compile(r"(?:sidebar|footer|nav)", re.IGNORECASE)


def _get_img_container_score(img_tag: Tag) -> int:
    """
    Score images by their container's relevance (article/main > aside/nav/header/footer).

    Higher score = more likely to be content
    """
    container = img_tag.parent
    while container:
        if (container_name := getattr(container, "name", None)) in ("article", "main"):
            return 2
        elif container_name in ("aside", "nav", "header", "footer"):
            return 0

        class_attr = container.get("class", [])
        if class_attr:
            if _GOOD_CLASS.search(
                class_str := " ".join(class_attr)
                if isinstance(class_attr, list)
                else class_attr
            ):
                return 2
            elif _BAD_CLASS.search(class_str):
                return 0

        container = getattr(container, "parent", None)
    return 1  # Default: neutral


def _aspect_ratio(width: int | float, height: int | float) -> float:
    width, height = float(width), float(height)
    if height == 0.0:
        return 0.0
    return width / height


def _usable_image_dimensions(
    img_src: str,
    response_max_byte_count: int,
    min_image_byte_count: int,
    min_image_width: int,
    min_image_height: int,
    min_image_aspect: float,
    max_image_aspect: float,
) -> tuple[int, int] | None:
    image_content: bytes
    try:
        with rss_requests.get(img_src, stream=True) as image_response:
            try:
                image_response.raise_for_status()
            except HTTPError as e:
                if image_response.status_code in (404,):
                    return None
                else:  # pragma: no cover
                    raise TryAgain from e

            content_type = image_response.headers.get("Content-Type")
            if content_type is None or not content_type_util.is_image(content_type):
                return None

            content_length_str = image_response.headers.get("Content-Length")
            if content_length_str is not None:
                try:
                    if int(content_length_str) < min_image_byte_count:
                        return None
                except ValueError:  # pragma: no cover
                    pass

            try:
                image_content = safe_response_content(
                    image_response, response_max_byte_count
                )
            except ResponseTooBig as e:  # pragma: no cover
                raise TryAgain from e
    except RequestException as e:  # pragma: no cover
        raise TryAgain from e

    try:
        with io.BytesIO(image_content) as f:
            with Image.open(f) as image:
                if image.format in ("GIF", "SVG"):
                    return None

                width, height = image.size
                if width < min_image_width or height < min_image_height:
                    return None

                img_aspect = _aspect_ratio(width, height)
                if img_aspect < min_image_aspect or img_aspect > max_image_aspect:
                    return None
    except UnidentifiedImageError:
        return None

    return width, height


class _ImageCandidate(NamedTuple):
    url: str
    width: int
    height: int
    container_score: int
    freq: int


def extract_top_image_src__experimental(
    url: str,
    response_max_byte_count: int,
    min_image_byte_count=4500,
    min_image_width=256,
    min_image_height=256,
    min_image_aspect=0.3,
    max_image_aspect=5.0,
    max_image_frequency=1,
    max_candidate_images=5,
):
    """
    Download the URL, parse HTML, and return a list of high-confidence banner/content image URLs,
    using multiple heuristics.
    """
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
    except RequestException as e:  # pragma: no cover
        raise TryAgain from e

    soup: BeautifulSoup
    try:
        soup = BeautifulSoup(response_text, "lxml")
    except Exception as e:  # pragma: no cover
        _logger.exception("unknown BeautifulSoup error")
        raise TryAgain from e

    # Extract keywords from page title for relevance
    page_title_keywords = frozenset(
        (soup.title.string.lower() if soup.title and soup.title.string else "").split()
    )

    meta_images: set[str] = set()

    # Collect images from OpenGraph (likely main/banner images)
    og: PageElement | Tag | NavigableString
    for og in soup.find_all("meta", property="og:image"):
        assert isinstance(og, Tag)
        if og_content := og.get("content"):
            assert isinstance(og_content, str)
            abs_url = urljoin(url, og_content)

            dim = _usable_image_dimensions(
                abs_url,
                response_max_byte_count,
                min_image_byte_count,
                min_image_width,
                min_image_height,
                min_image_aspect,
                max_image_aspect,
            )

            if dim is None:
                continue

            meta_images.add(abs_url)

    # Collect images from Twitter Cards (optional, similar to OpenGraph)
    tw: PageElement | Tag | NavigableString
    for tw in soup.find_all("meta", attrs={"name": "twitter:image"}):
        assert isinstance(tw, Tag)
        if tw_content := tw.get("content"):
            assert isinstance(tw_content, str)
            abs_url = urljoin(url, tw_content)

            dim = _usable_image_dimensions(
                abs_url,
                response_max_byte_count,
                min_image_byte_count,
                min_image_width,
                min_image_height,
                min_image_aspect,
                max_image_aspect,
            )

            if dim is None:
                continue

            meta_images.add(abs_url)

    image_candidates: list[_ImageCandidate] = []

    # Collect all <img> tags and score/filter them
    img_seen: set[str] = set()
    img_tag: PageElement | Tag | NavigableString
    for img_tag in soup.find_all("img"):
        assert isinstance(img_tag, Tag)
        src = img_tag.get("src")
        if not src:
            continue

        assert isinstance(src, str)

        abs_url = urljoin(url, src)

        if abs_url in img_seen:
            continue
        img_seen.add(abs_url)

        if _is_probably_decorative(img_tag, abs_url, page_title_keywords):
            continue

        dim = _usable_image_dimensions(
            abs_url,
            response_max_byte_count,
            min_image_byte_count,
            min_image_width,
            min_image_height,
            min_image_aspect,
            max_image_aspect,
        )

        if dim is None:
            continue

        width, height = dim

        # Score container relevance (main/article > nav/header/aside)
        container_score = _get_img_container_score(img_tag)

        # Count occurrences (images used many times are likely decorative)
        freq = len(soup.find_all("img", {"src": src}))

        image_candidates.append(
            _ImageCandidate(
                abs_url,
                width,
                height,
                container_score,
                freq,
            )
        )

    # Sort image candidates by container score, frequency (prefer unique), size
    image_candidates.sort(
        key=lambda x: (
            -x.container_score,  # Prefer main/article containers
            x.freq,  # Prefer less frequently used images
            -(x.width or 0) * (x.height or 0),  # Prefer larger images
        )
    )

    # Combine all high-confidence images (OpenGraph, schema, best img candidates)
    result_urls: list[str] = []
    result_urls.extend(meta_images)
    result_urls.extend(
        [img.url for img in image_candidates if img.freq > max_image_frequency][
            :max_candidate_images
        ]
    )

    return result_urls
