import math
import os
from typing import Any

import ujson
from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    help = "Break a large fixture into many smaller fixtures"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("fixture_filepath")
        parser.add_argument("to_dirpath")
        parser.add_argument("--chunk-size", default=1000, type=int)

    def handle(self, *args: Any, **options: Any) -> None:
        fixture_json: list[dict[str, Any]]
        with open(options["fixture_filepath"], "r") as f:
            fixture_json = ujson.load(f)

        self.stderr.write(f"contains {len(fixture_json)} entries")

        os.makedirs(options["to_dirpath"], exist_ok=True, mode=0o777)

        model_types = frozenset(j["model"] for j in fixture_json)

        for model_type in model_types:
            model_json = [j for j in fixture_json if j["model"] == model_type]

            right_justify_count = len(
                str(math.ceil(len(model_json) / options["chunk_size"]))
            )
            for i, chunk in enumerate(
                _chunk_list(
                    model_json,
                    options["chunk_size"],
                )
            ):
                self.stderr.write(f"{i}")
                rjust_num = str(i).rjust(right_justify_count, "0")
                with open(
                    os.path.join(
                        options["to_dirpath"], f"{model_type}.{rjust_num}.json"
                    ),
                    "w",
                ) as f:
                    ujson.dump(chunk, f, ensure_ascii=False)


def _chunk_list(l: list, chunk_size: int):
    assert chunk_size > 0

    for i in range(0, len(l), chunk_size):
        yield l[i : i + chunk_size]
