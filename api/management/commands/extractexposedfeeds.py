import pprint
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from api.exposed_feed_extractor import extract_exposed_feeds


class Command(BaseCommand):
    help = "Find exposed feeds"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("url")

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        exposed_feeds = extract_exposed_feeds(
            options["url"],
            response_max_size=settings.DOWNLOAD_MAX_SIZE,
        )
        self.stderr.write(
            self.style.NOTICE(
                "exposed feeds:\n{exposed_feeds}".format(
                    exposed_feeds=pprint.pformat(exposed_feeds)
                )
            )
        )
