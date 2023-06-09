import html
import re
from typing import Any
from urllib.parse import urlparse

import bleach
import bleach.html5lib_shim
import bleach.sanitizer
import html5lib
from html5lib.filters.base import Filter as HTML5LibFilter
from html5lib.treewalkers.base import TreeWalker


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


_bad_iframe_url_fns = [
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
                        src_url = None
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
        tags = set(bleach.sanitizer.ALLOWED_TAGS)
        tags.add("p")
        tags.add("img")
        tags.add("br")
        tags.add("iframe")

        attributes = dict(bleach.sanitizer.ALLOWED_ATTRIBUTES)
        attributes["img"] = ["src"]
        attributes["iframe"] = ["src", "title", "width", "height", "allowfullscreen"]

        styles = set(bleach.sanitizer.ALLOWED_STYLES)

        protocols = set(bleach.sanitizer.ALLOWED_PROTOCOLS)

        _my_bleach_filter_kwargs_ = {
            # see https://github.com/mozilla/bleach/blob/3e5d6aa375677821aaf249127e44ac51a815cf2b/bleach/sanitizer.py#L179
            "attributes": attributes,
            "strip_disallowed_elements": True,
            "strip_html_comments": True,
            # see https://github.com/mozilla/bleach/blob/3e5d6aa375677821aaf249127e44ac51a815cf2b/bleach/sanitizer.py#L183
            "allowed_elements": tags,
            "allowed_css_properties": styles,
            "allowed_protocols": protocols,
            "allowed_svg_properties": [],
        }

    filtered = ScriptRemovalFiler(source=source)
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
