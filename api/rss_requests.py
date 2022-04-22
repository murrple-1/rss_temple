import requests


def get(url, headers: dict[str, str] | None = None, *args, **kwargs):
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
