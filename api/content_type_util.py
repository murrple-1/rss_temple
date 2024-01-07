import re


class WrongContentTypeError(Exception):
    pass


def is_html(content_type: str) -> bool:
    return any(
        re.search(re_str, content_type, re.IGNORECASE)
        for re_str in (r"text/html", "application/xhtml+xml")
    )


def is_feed(content_type: str) -> bool:
    return any(
        re.search(re_str, content_type, re.IGNORECASE)
        for re_str in (
            r"application/(?:rss|rdf|atom)\+xml",
            r"application/xml",
            r"text/xml",
            r"application/json",
        )
    )
