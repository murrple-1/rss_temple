import ipaddress
import socket
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from requests.exceptions import RequestException, TooManyRedirects

_BLOCK_PRIVATE_ADDRESSES: bool

_MAX_REDIRECTS = 10


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _BLOCK_PRIVATE_ADDRESSES

    _BLOCK_PRIVATE_ADDRESSES = settings.RSS_REQUESTS_BLOCK_PRIVATE_ADDRESSES


_load_global_settings()


class UnsafeURLError(RequestException):
    """Raised when a request target resolves to a non-public (SSRF-prone) address.

    Subclasses `RequestException` so existing callers that already treat network
    failures as "feed not found" / skip handle unsafe URLs gracefully.
    """


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # normalize IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) back to IPv4
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_url_is_public(url: str | bytes) -> None:
    if isinstance(url, bytes):
        url = url.decode("utf-8", errors="replace")

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"disallowed URL scheme: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL has no host")

    try:
        addrinfos = socket.getaddrinfo(hostname, parsed.port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise UnsafeURLError(f"unable to resolve host: {hostname!r}") from e

    # reject if *any* resolved address is non-public; do not fetch from a host
    # that (partly) points at internal infrastructure.
    for *_, sockaddr in addrinfos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:  # pragma: no cover
            raise UnsafeURLError(f"unable to parse resolved address: {sockaddr[0]!r}")

        if not _is_public_ip(ip):
            raise UnsafeURLError(
                f"host {hostname!r} resolves to non-public address {ip}"
            )


def get(
    url: str | bytes,
    headers: Mapping[str, str | bytes] | None = None,
    timeout=30,
    *args: Any,
    **kwargs: Any,
):
    headers = {
        "User-Agent": "RSS Temple",
        **(headers or {}),
    }

    if not _BLOCK_PRIVATE_ADDRESSES:
        return requests.get(url, timeout=timeout, headers=headers, *args, **kwargs)

    # When guarding against SSRF we must validate every hop: `requests` would
    # otherwise follow a redirect to an internal address after our check on the
    # initial URL passed. So follow redirects manually, revalidating each time.
    allow_redirects = kwargs.pop("allow_redirects", True)

    current_url: str | bytes = url
    for _ in range(_MAX_REDIRECTS + 1):
        _validate_url_is_public(current_url)

        response = requests.get(
            current_url,
            timeout=timeout,
            headers=headers,
            allow_redirects=False,
            *args,
            **kwargs,
        )

        if not (allow_redirects and response.is_redirect):
            return response

        location = response.headers.get("Location")
        if not location:  # pragma: no cover
            return response

        next_url = urljoin(
            current_url.decode() if isinstance(current_url, bytes) else current_url,
            location,
        )
        # release the intermediate (possibly streamed) connection before the
        # next hop
        response.close()
        current_url = next_url

    raise TooManyRedirects(f"exceeded {_MAX_REDIRECTS} redirects")
