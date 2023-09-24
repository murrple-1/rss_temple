from typing import Any, Mapping

import requests


def get(
    url: str | bytes,
    headers: Mapping[str, str | bytes] | None = None,
    *args: Any,
    **kwargs: Any
):
    headers = headers or {}
    return requests.get(
        url,
        timeout=30,
        headers={
            **headers,
            **{
                "User-Agent": "RSS Temple",
            },
        },
        *args,
        **kwargs,
    )


def head(
    url: str | bytes,
    headers: Mapping[str, str | bytes] | None = None,
    *args: Any,
    **kwargs: Any
):
    headers = headers or {}
    return requests.head(
        url,
        timeout=30,
        headers={
            **headers,
            **{
                "User-Agent": "RSS Temple",
            },
        },
        *args,
        **kwargs,
    )
