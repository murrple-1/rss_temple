import requests
from django.test import tag

from api import requests_extensions
from api.tests import TestFileServerTestCase


class RequestsExtensionsTestCase(TestFileServerTestCase):
    @tag("slow")
    def test_safe_response_content(self):
        response = requests.get(
            f"{RequestsExtensionsTestCase.live_server_url}/site/16bytes.txt"
        )

        content = requests_extensions.safe_response_content(response, 16, 1024)
        self.assertEqual(len(content), 16)

        response = requests.get(
            f"{RequestsExtensionsTestCase.live_server_url}/site/16bytes.txt"
        )

        with self.assertRaises(requests.exceptions.RequestException):
            requests_extensions.safe_response_content(response, 15, 1024)

    @tag("slow")
    def test_safe_response_text(self):
        response = requests.get(
            f"{RequestsExtensionsTestCase.live_server_url}/site/16bytes.txt"
        )

        text = requests_extensions.safe_response_text(response, 16, 1024)
        self.assertEqual(len(text), 16)

        response = requests.get(
            f"{RequestsExtensionsTestCase.live_server_url}/site/16bytes.txt"
        )

        with self.assertRaises(requests.exceptions.RequestException):
            requests_extensions.safe_response_text(response, 15, 1024)
