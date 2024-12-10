from typing import Any, Mapping

import requests


def get(
    url: str | bytes,
    headers: Mapping[str, str | bytes] | None = None,
    timeout=30,
    *args: Any,
    **kwargs: Any,
):
    headers = headers or {}
    return requests.get(
        url,
        timeout=timeout,
        headers={
            **{
                "User-Agent": "RSS Temple",
            },
            **headers,
        },
        *args,
        **kwargs,
    )
