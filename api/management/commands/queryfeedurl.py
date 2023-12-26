from typing import Any, cast

from django.core.management.base import CommandParser
from url_normalize import url_normalize

from api.management.commands._queryfeedurlbase import BaseCommand


class Command(BaseCommand):
    help = "Tool to query real RSS feeds, and potentially force them into the DB"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("feed_url")
        parser.add_argument("-s", "--save", action="store_true")
        parser.add_argument("-f", "--print-feed", action="store_true")
        parser.add_argument("-e", "--print-entries", action="store_true")
        parser.add_argument("-c", "--with-content", action="store_true")
        parser.add_argument("-m", "--max-db-feed-entries", type=int, default=20)

    def handle(self, *args: Any, **options: Any):
        self._query_feed_url(
            [cast(str, url_normalize(options["feed_url"]))],
            save=options["save"],
            print_feeds=options["print_feed"],
            print_entries=options["print_entries"],
            with_content=options["with_content"],
            max_db_feed_entries=options["max_db_feed_entries"],
        )
