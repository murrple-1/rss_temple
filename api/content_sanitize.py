import html
import re
from typing import Any, Callable
from urllib.parse import ParseResult, urlparse

import bleach
import bleach.css_sanitizer
import bleach.sanitizer
import html5lib
from bleach.html5lib_shim import SanitizerFilter as HTML5ShimFilter
from html5lib.filters.base import Filter as HTML5LibFilter
from html5lib.treewalkers.base import TreeWalker

# TODO add filter so anchors automatically open in new tabs


class TagRemovalFilter(HTML5LibFilter):
    def __init__(self, *args: Any, **kwargs: Any):
        self.tag = kwargs.pop("tag")
        super().__init__(*args, **kwargs)

    def __iter__(self):
        tag_depth = 0
        for token in super().__iter__():
            if token["type"] == "StartTag" and token["name"] == self.tag:
                tag_depth += 1
            elif token["type"] == "EndTag" and token["name"] == self.tag:
                tag_depth -= 1
            else:
                if tag_depth <= 0:
                    yield token


class ScriptRemovalFiler(TagRemovalFilter):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, tag="script", **kwargs)


class StyleRemovalFiler(TagRemovalFilter):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, tag="style", **kwargs)


class HTTPSOnlyImgFilter(HTML5LibFilter):
    def __iter__(self):
        for token in super().__iter__():
            if token["type"] == "EmptyTag" and token["name"] == "img":
                data = token["data"]
                if (None, "src") in data and not data[(None, "src")].startswith(
                    "https://"
                ):
                    continue

            yield token


class EmptyAnchorFilter(HTML5LibFilter):
    def __iter__(self):
        tag_depth = 0
        seen_tokens: list[dict[str, Any]] = []
        for token in super().__iter__():
            if token["type"] == "StartTag" and token["name"] == "a":
                tag_depth += 1
                seen_tokens.append(token)
            elif token["type"] == "EndTag" and token["name"] == "a":
                tag_depth -= 1
                seen_tokens.append(token)

                if tag_depth <= 0:
                    if any(
                        True
                        if (t["type"] == "Characters" and len(t["data"]) > 0)
                        else False
                        for t in seen_tokens
                    ):
                        for t in seen_tokens:
                            yield t

                    seen_tokens = []
            else:
                if tag_depth > 0:
                    seen_tokens.append(token)
                else:
                    yield token


_bad_iframe_url_fns: list[Callable[[ParseResult], bool]] = [
    lambda url: url.netloc == "slashdot.org",
]


class BadIFrameFilter(HTML5LibFilter):
    def __iter__(self):
        is_in_bad_iframe = False
        for token in super().__iter__():
            if is_in_bad_iframe:
                if token["type"] == "EndTag" and token["name"] == "iframe":
                    is_in_bad_iframe = False
            else:
                if token["type"] == "StartTag" and token["name"] == "iframe":
                    data = token["data"]
                    if (None, "src") in data:
                        src_url: ParseResult
                        try:
                            src_url = urlparse(data[(None, "src")])
                        except ValueError:
                            is_in_bad_iframe = True
                            continue

                        found_bad_iframe = False
                        for bad_iframe_url_fn in _bad_iframe_url_fns:
                            if bad_iframe_url_fn(src_url):
                                found_bad_iframe = True
                                break

                        if found_bad_iframe:
                            is_in_bad_iframe = True
                            continue
                    else:
                        is_in_bad_iframe = True
                        continue

                yield token


_my_bleach_filter_kwargs_: dict[str, Any] | None = None


def _html_sanitizer_stream(source: TreeWalker):
    global _my_bleach_filter_kwargs_
    if _my_bleach_filter_kwargs_ is None:
        allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS)
        allowed_tags.add("p")
        allowed_tags.add("img")
        allowed_tags.add("br")
        allowed_tags.add("iframe")

        allowed_attributes = dict(bleach.sanitizer.ALLOWED_ATTRIBUTES)
        allowed_attributes["img"] = ["src"]
        allowed_attributes["iframe"] = [
            "src",
            "title",
            "width",
            "height",
            "allowfullscreen",
        ]

        allowed_protocols = set(bleach.sanitizer.ALLOWED_PROTOCOLS)

        allowed_css_properties = set(bleach.css_sanitizer.ALLOWED_CSS_PROPERTIES)

        allowed_svg_properties = set(bleach.css_sanitizer.ALLOWED_SVG_PROPERTIES)

        css_sanitizer = bleach.css_sanitizer.CSSSanitizer(
            allowed_css_properties=allowed_css_properties,
            allowed_svg_properties=allowed_svg_properties,
        )

        _my_bleach_filter_kwargs_ = {
            "attributes": allowed_attributes,
            "strip_disallowed_tags": True,
            "strip_html_comments": True,
            "allowed_tags": allowed_tags,
            "allowed_protocols": allowed_protocols,
            "css_sanitizer": css_sanitizer,
        }

    filtered: HTML5LibFilter | HTML5ShimFilter = ScriptRemovalFiler(source=source)
    filtered = StyleRemovalFiler(source=filtered)
    filtered = HTTPSOnlyImgFilter(source=filtered)
    filtered = EmptyAnchorFilter(source=filtered)
    filtered = BadIFrameFilter(source=filtered)
    filtered = bleach.sanitizer.BleachSanitizerFilter(
        source=filtered, **_my_bleach_filter_kwargs_
    )

    return filtered


_is_html_regex = re.compile(r"<\/?[a-z][\s\S]*>", re.IGNORECASE)


def is_html(text: str):
    return _is_html_regex.search(text) is not None


def sanitize(text: str):
    if is_html(text):
        return sanitize_html(text)
    else:
        return sanitize_plain(text)


_html_serializer = html5lib.serializer.HTMLSerializer(resolve_entities=False)


def sanitize_html(text: str):
    dom = html5lib.parse(text, treebuilder="lxml")
    walker = html5lib.getTreeWalker("lxml")
    stream = _html_sanitizer_stream(walker(dom))
    return _html_serializer.render(stream)


def sanitize_plain(text: str):
    return "<br>".join(html.escape(text).splitlines())
