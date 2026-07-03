import re
from typing import Any
from urllib.parse import urlparse

import bleach
import bleach.sanitizer
import html5lib
from bleach.html5lib_shim import SanitizerFilter as HTML5ShimFilter
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


class ScriptRemovalFilter(TagRemovalFilter):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, tag="script", **kwargs)


class StyleRemovalFilter(TagRemovalFilter):
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
                        (
                            True
                            if (t["type"] == "Characters" and len(t["data"]) > 0)
                            else False
                        )
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


# iframes are only preserved when their `src` points at a known, trusted embed
# host over HTTPS. This is an allowlist (safe by default): anything not matched
# — including src-less and malformed-src iframes — is dropped entirely.
_ALLOWED_IFRAME_HOSTS: frozenset[str] = frozenset(
    {
        "youtube.com",
        "youtube-nocookie.com",
        "vimeo.com",
        "player.vimeo.com",
        "dailymotion.com",
        "w.soundcloud.com",
        "open.spotify.com",
        "player.twitch.tv",
        "bandcamp.com",
    }
)


def _is_allowed_iframe_src(src: str) -> bool:
    try:
        url = urlparse(src)
        if url.scheme != "https":
            return False
        hostname = url.hostname
    except ValueError:
        return False

    if not hostname:
        return False

    hostname = hostname.lower()
    return any(
        hostname == allowed or hostname.endswith(f".{allowed}")
        for allowed in _ALLOWED_IFRAME_HOSTS
    )


class AllowlistIFrameFilter(HTML5LibFilter):
    def __iter__(self):
        is_in_disallowed_iframe = False
        for token in super().__iter__():
            if is_in_disallowed_iframe:
                if token["type"] == "EndTag" and token["name"] == "iframe":
                    is_in_disallowed_iframe = False
            else:
                if token["type"] == "StartTag" and token["name"] == "iframe":
                    data = token["data"]
                    src = data[(None, "src")] if (None, "src") in data else None
                    if not src or not _is_allowed_iframe_src(src):
                        is_in_disallowed_iframe = True
                        continue

                yield token


class AnchorsOpenNewTabFilter(HTML5LibFilter):
    def __iter__(self):
        for token in super().__iter__():
            if token["type"] == "StartTag" and token["name"] == "a":
                token["data"][(None, "target")] = "_blank"
                # Prevent reverse tabnabbing: the opened page must not be able
                # to reach back to this tab via `window.opener`.
                token["data"][(None, "rel")] = "noopener noreferrer"

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
        allowed_attributes["a"] = ["href", "title", "target", "rel"]

        allowed_protocols = set(bleach.sanitizer.ALLOWED_PROTOCOLS)

        _my_bleach_filter_kwargs_ = {
            "attributes": allowed_attributes,
            "strip_disallowed_tags": True,
            "strip_html_comments": True,
            "allowed_tags": allowed_tags,
            "allowed_protocols": allowed_protocols,
        }

    filtered: HTML5LibFilter | HTML5ShimFilter = ScriptRemovalFilter(source=source)
    filtered = StyleRemovalFilter(source=filtered)
    filtered = HTTPSOnlyImgFilter(source=filtered)
    filtered = EmptyAnchorFilter(source=filtered)
    filtered = AllowlistIFrameFilter(source=filtered)
    filtered = AnchorsOpenNewTabFilter(source=filtered)
    filtered = bleach.sanitizer.BleachSanitizerFilter(
        source=filtered, **_my_bleach_filter_kwargs_
    )

    return filtered


_has_tags = re.compile(r"<\/?[a-z][\s\S]*>", re.IGNORECASE)


def sanitize(text: str) -> str:
    if _has_tags.search(text) is not None:
        return _sanitize_html(text)
    else:
        return _sanitize_html("<br>".join(text.splitlines()))


_html_serializer = html5lib.serializer.HTMLSerializer(
    resolve_entities=False,
    quote_attr_values="always",
    alphabetical_attributes=True,
    strip_whitespace=True,
)


def _sanitize_html(text: str) -> str:
    dom = html5lib.parse(text, treebuilder="lxml")
    walker = html5lib.getTreeWalker("lxml")
    stream = _html_sanitizer_stream(walker(dom))
    return _html_serializer.render(stream)
