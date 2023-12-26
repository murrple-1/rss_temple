from typing import Any
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring as defused_fromstring
from django.core.management.base import CommandParser

from api import opml as opml_util
from api.management.commands._queryfeedurlbase import BaseCommand


class Command(BaseCommand):
    help = "Tool to query real RSS feeds, and potentially force them into the DB"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("opml_filepath")
        parser.add_argument("-s", "--save", action="store_true")
        parser.add_argument("-f", "--print-feed", action="store_true")
        parser.add_argument("-e", "--print-entries", action="store_true")
        parser.add_argument("-c", "--with-content", action="store_true")
        parser.add_argument("-m", "--max-db-feed-entries", type=int, default=20)

    def handle(self, *args: Any, **options: Any):
        opml_element: Element
        with open(options["opml_filepath"], "r") as f:
            opml_element = defused_fromstring(f.read())

        opml_util.schema().validate(opml_element)

        grouped_entries = opml_util.get_grouped_entries(opml_element)

        feed_urls = frozenset(t.url for e in grouped_entries.values() for t in e)

        self._query_feed_url(
            feed_urls,
            save=options["save"],
            print_feed=options["print_feed"],
            print_entries=options["print_entries"],
            with_content=options["with_content"],
            max_db_feed_entries=options["max_db_feed_entries"],
        )
