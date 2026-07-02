import ipaddress
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from requests.exceptions import RequestException

from api import rss_requests
from api.tests import TestFileServerTestCase


class IsPublicIpTestCase(SimpleTestCase):
    def test_blocks_non_public(self):
        for addr in (
            "127.0.0.1",
            "10.0.0.1",
            "192.168.1.1",
            "172.16.0.1",
            "169.254.169.254",  # link-local / cloud metadata
            "0.0.0.0",
            "::1",
            "fe80::1",
            "::ffff:127.0.0.1",  # IPv4-mapped loopback
        ):
            with self.subTest(addr=addr):
                self.assertFalse(rss_requests._is_public_ip(ipaddress.ip_address(addr)))

    def test_allows_public(self):
        for addr in ("8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"):
            with self.subTest(addr=addr):
                self.assertTrue(rss_requests._is_public_ip(ipaddress.ip_address(addr)))

    def test_validate_url_rejects_non_http_scheme(self):
        for url in ("file:///etc/passwd", "ftp://example.com/x", "gopher://x/"):
            with self.subTest(url=url):
                with self.assertRaises(RequestException):
                    rss_requests._validate_url_is_public(url)


@override_settings(RSS_REQUESTS_BLOCK_PRIVATE_ADDRESSES=True)
class BlockingEnabledTestCase(TestFileServerTestCase):
    def test_preflight_blocks_loopback(self):
        # the live server binds to loopback, which the pre-flight DNS check
        # rejects before any connection is made
        with self.assertRaises(RequestException):
            rss_requests.get(f"{self.live_server_url}/")

    def test_connect_time_blocks_loopback(self):
        # bypass the pre-flight lookup to prove the connect-time peer check (the
        # DNS-rebinding guard) independently blocks a loopback peer: the socket
        # connects successfully, then is rejected on its real address
        with patch.object(rss_requests, "_validate_url_is_public", lambda url: None):
            with self.assertRaises(RequestException) as cm:
                rss_requests.get(f"{self.live_server_url}/")

        self.assertIn("non-public", str(cm.exception))
