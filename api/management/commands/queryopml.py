import glob
from typing import Any
from xml.etree.ElementTree import Element

import xmlschema
from defusedxml.ElementTree import ParseError as defused_ParseError
from defusedxml.ElementTree import fromstring as defused_fromstring
from django.core.management.base import CommandError, CommandParser

from api import opml as opml_util
from api.management.commands._queryfeedurlbase import BaseCommand


class Command(BaseCommand):
    help = "Tool to query real RSS feeds, and potentially force them into the DB"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("opml_filepaths", nargs="+")
        parser.add_argument("-s", "--save", action="store_true")
        parser.add_argument("-f", "--print-feeds", action="store_true")
        parser.add_argument("-e", "--print-entries", action="store_true")
        parser.add_argument("-c", "--with-content", action="store_true")
        parser.add_argument("-m", "--max-db-feed-entries", type=int, default=20)

    def handle(self, *args: Any, **options: Any):
        feed_urls: set[str] = set()

        for opml_filepath_glob in options["opml_filepaths"]:
            for opml_filepath in glob.glob(opml_filepath_glob):
                self.stderr.write(self.style.NOTICE(f"reading '{opml_filepath}'..."))

                opml_element: Element
                with open(opml_filepath, "r") as f:
                    try:
                        opml_element = defused_fromstring(f.read())
                    except defused_ParseError as e:
                        raise CommandError(e.msg)

                try:
                    opml_util.schema().validate(opml_element)
                except xmlschema.XMLSchemaException as e:
                    raise CommandError(str(e))

                grouped_entries = opml_util.get_grouped_entries(opml_element)

                feed_urls.update(t.url for e in grouped_entries.values() for t in e)

        self._query_feed_url(
            sorted(feed_urls),
            save=options["save"],
            print_feeds=options["print_feeds"],
            print_entries=options["print_entries"],
            with_content=options["with_content"],
            max_db_feed_entries=options["max_db_feed_entries"],
            verbosity=options["verbosity"],
        )
