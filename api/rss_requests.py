from typing import Any, Mapping

import requests


def get(
    url, headers: Mapping[str, str | bytes] | None = None, *args: Any, **kwargs: Any
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
        **kwargs
    )
