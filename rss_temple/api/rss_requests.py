import requests


def get(url, headers=None, *args, **kwargs):
    headers = headers or {}
    return requests.get(url, headers={**headers, **{
        'User-Agent': 'RSS Temple',
    }}, *args, **kwargs)
