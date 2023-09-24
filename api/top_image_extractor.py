import io
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup, ResultSet, Tag
from PIL import Image

from api import rss_requests


def is_top_image_needed(content: str) -> bool:
    soup = BeautifulSoup(content, "lxml")
    return len(soup.findAll("img")) < 1


def extract_top_image_src(
    url: str,
    min_image_byte_count=4500,
    min_image_width=512,
    min_image_height=512,
) -> str | None:
    r = rss_requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, "lxml")

    testable_img_tags: ResultSet[Tag] = soup.find_all(_img_with_conditions)

    testable_image_properties: list[_ImageProperties] = []
    for img_tag in testable_img_tags:
        src = img_tag["src"]
        assert isinstance(src, str)

        transformed_srcs = _src_to_possible_srcs(src, url)
        print(transformed_srcs)

        for transformed_src in transformed_srcs:
            content_size_large_enough, content = _content_size_test(
                transformed_src, min_image_byte_count
            )
            if not content_size_large_enough:
                continue

            assert content is not None

            with io.BytesIO(content) as f:
                with Image.open(f) as image:
                    testable_image_properties.append(
                        _ImageProperties(transformed_src, image.width, image.height)
                    )

            break

    testable_image_properties = [
        tim
        for tim in testable_image_properties
        if tim.width > min_image_width and tim.height > min_image_height
    ]

    if len(testable_image_properties) < 1:
        return None

    testable_image_properties.sort(key=lambda im: im.width * im.height)

    return testable_image_properties[0].src


def _img_with_conditions(tag: Tag) -> bool:
    if tag.name != "img":
        return False

    src = tag.get("src")
    if not src:
        return False

    if not isinstance(src, str):
        return False

    src_url = urlparse(src)

    if src_url.scheme not in ("", "http", "https"):
        return False

    # TODO implement conditions
    # eg "advert" not in tag.parent["class"]

    return True


def _content_size_test(
    src: str | bytes, min_image_byte_count: int
) -> tuple[bool, bytes | None]:
    content_size_tested = False

    if not content_size_tested:
        image_head_r = rss_requests.head(src)
        image_head_r.raise_for_status()

        content_size_str = image_head_r.headers.get("Content-Size")
        if content_size_str is not None:
            try:
                if int(content_size_str) < min_image_byte_count:
                    return False, None

                content_size_tested = True
            except ValueError:
                pass

    image_r = rss_requests.get(src)
    image_r.raise_for_status()

    if not content_size_tested:
        if len(image_r.content) < min_image_byte_count:
            return False, None

    return True, image_r.content


def _src_to_possible_srcs(src: str, containing_url: str) -> list[str]:
    print(f"{src=}")
    src_url = urlparse(src)
    print(f"{src_url=}")

    if not src_url.netloc:
        url_ = urlparse(containing_url)
        src_url = src_url._replace(netloc=url_.netloc)

    if not src_url.scheme:
        return [
            src_url._replace(scheme="https").geturl(),
            src_url._replace(scheme="http").geturl(),
        ]
    else:
        return [src_url.geturl()]


@dataclass(slots=True)
class _ImageProperties:
    src: str
    width: int
    height: int
