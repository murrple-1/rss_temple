import pprint
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from api import feed_handler, rss_requests
from api.requests_extensions import safe_response_text


class Command(BaseCommand):
    help = "Download a feed, parse it using our feed handler lib, and print the output"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("feed_url")

    def handle(self, *args: Any, **options: Any) -> None:
        with rss_requests.get(options["feed_url"], stream=True) as response:
            response.raise_for_status()
            response_text = safe_response_text(
                response,
                settings.DOWNLOAD_MAX_BYTE_COUNT,
            )

            d = feed_handler.text_2_d(response_text)
            pprint.pprint(d)
