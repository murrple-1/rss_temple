import re


class WrongContentTypeError(Exception):
    pass


def is_html(content_type: str) -> bool:
    return (
        re.search(r"(?:text/html|application/xhtml\+xml)", content_type, re.IGNORECASE)
        is not None
    )


def is_feed(content_type: str) -> bool:
    return (
        re.search(
            r"(?:application/(?:(?:(?:rss|rdf|atom)\+)?xml|json)|text/xml)",
            content_type,
            re.IGNORECASE,
        )
        is not None
    )
