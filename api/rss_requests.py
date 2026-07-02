import ipaddress
import socket
from typing import Any, Mapping
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.poolmanager import PoolManager

_BLOCK_PRIVATE_ADDRESSES: bool


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _BLOCK_PRIVATE_ADDRESSES

    _BLOCK_PRIVATE_ADDRESSES = settings.RSS_REQUESTS_BLOCK_PRIVATE_ADDRESSES


_load_global_settings()


class UnsafeURLError(RequestException):
    """Raised when a request target resolves/connects to a non-public address.

    Subclasses `RequestException` (itself an `OSError`) so existing callers that
    already treat network failures as "feed not found" / skip handle unsafe URLs
    gracefully. When raised at connect time it surfaces wrapped in a
    `requests.exceptions.ConnectionError`, which is likewise a `RequestException`.
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
    """Fast pre-flight rejection: disallow non-HTTP(S) schemes and hosts whose
    DNS records point (even partly) at non-public space, before a connection is
    attempted.

    This is a convenience short-circuit for clean early errors. The
    authoritative guard is `_PeerValidationMixin`, which inspects the *actual*
    connected peer and so — unlike this lookup — is not subject to a
    DNS-rebinding race between resolution and the real connection.
    """
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

    for *_, sockaddr in addrinfos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:  # pragma: no cover
            raise UnsafeURLError(f"unable to parse resolved address: {sockaddr[0]!r}")

        if not _is_public_ip(ip):
            raise UnsafeURLError(
                f"host {hostname!r} resolves to non-public address {ip}"
            )


class _PeerValidationMixin:
    """Validates the *actual* connected peer, closing the DNS-rebinding gap: the
    address we check is exactly the address the socket connected to, so a rebind
    between a pre-flight lookup and the real connection cannot slip through. No
    application data is sent until the peer is confirmed public."""

    def _new_conn(self) -> socket.socket:
        sock = super()._new_conn()  # type: ignore[misc]

        try:
            peer_ip = ipaddress.ip_address(sock.getpeername()[0])
        except (OSError, ValueError) as e:
            sock.close()
            raise UnsafeURLError("unable to determine peer address") from e

        if not _is_public_ip(peer_ip):
            sock.close()
            raise UnsafeURLError(
                f"connection established to non-public address {peer_ip}"
            )

        return sock


class _ValidatingHTTPConnection(_PeerValidationMixin, HTTPConnection):
    pass


class _ValidatingHTTPSConnection(_PeerValidationMixin, HTTPSConnection):
    pass


class _ValidatingHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _ValidatingHTTPConnection


class _ValidatingHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _ValidatingHTTPSConnection


class _ValidatingPoolManager(PoolManager):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.pool_classes_by_scheme = {
            "http": _ValidatingHTTPConnectionPool,
            "https": _ValidatingHTTPSConnectionPool,
        }


class _SSRFValidatingAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        self.poolmanager = _ValidatingPoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs,
        )


_ssrf_safe_session: requests.Session | None = None


def _get_ssrf_safe_session() -> requests.Session:
    global _ssrf_safe_session
    if _ssrf_safe_session is None:
        session = requests.Session()
        adapter = _SSRFValidatingAdapter()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _ssrf_safe_session = session
    return _ssrf_safe_session


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

    # Fast pre-flight rejection (clean errors, blocks non-HTTP schemes). Every
    # actual connection — including each redirect hop — is then independently
    # validated against its real peer address by `_SSRFValidatingAdapter`, so
    # there is no DNS-rebinding window.
    _validate_url_is_public(url)

    session = _get_ssrf_safe_session()
    return session.get(url, timeout=timeout, headers=headers, *args, **kwargs)
