import json
from typing import Any

from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    help = "TEMP: Convert old fixtures to new"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("fixture_filepath")

    def handle(self, *args: Any, **options: Any) -> None:
        fixture_json: list[dict[str, Any]]
        with open(options["fixture_filepath"], "r") as f:
            fixture_json = json.load(f)

        for feed_user_category_mapping_json in filter(
            (lambda j: j["model"] == "api.feedusercategorymapping"), fixture_json
        ):
            user_category_json = next(
                j
                for j in fixture_json
                if j["model"] == "api.usercategory"
                and feed_user_category_mapping_json["fields"]["user_category"]
                == j["pk"]
            )
            if "feeds" not in user_category_json["fields"]:
                user_category_json["fields"]["feeds"] = []

            user_category_json["fields"]["feeds"].append(
                feed_user_category_mapping_json["fields"]["feed"]
            )

        fixture_json = [
            j for j in fixture_json if j["model"] != "api.feedusercategorymapping"
        ]

        with open(options["fixture_filepath"], "w") as f:
            json.dump(fixture_json, f, indent=2, ensure_ascii=False)
