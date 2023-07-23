from typing import Any

import ujson
from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    help = "TEMP: Convert old fixtures to new"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("fixture_filepath")
        parser.add_argument("to_filepath")

    def handle(self, *args: Any, **options: Any) -> None:
        fixture_json: list[dict[str, Any]]
        with open(options["fixture_filepath"], "r") as f:
            fixture_json = ujson.load(f)

        fixture_json = [
            json_
            for json_ in fixture_json
            if json_["model"]
            not in ("api.googlelogin", "api.facebooklogin", "api.verificationtoken")
        ]

        for mylogin_json in filter(
            (lambda j: j["model"] == "api.mylogin"), fixture_json
        ):
            user_json = next(
                j
                for j in fixture_json
                if j["model"] == "api.user"
                and mylogin_json["fields"]["user"] == j["pk"]
            )

            user_json["fields"]["password"] = (
                "argon2" + mylogin_json["fields"]["pw_hash"]
            )

        fixture_json = [
            json_ for json_ in fixture_json if json_["model"] != "api.mylogin"
        ]

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

        for favorite_feed_entry_user_mapping_json in filter(
            (lambda j: j["model"] == "api.favoritefeedentryusermapping"), fixture_json
        ):
            user_json = next(
                j
                for j in fixture_json
                if j["model"] == "api.user"
                and favorite_feed_entry_user_mapping_json["fields"]["user"] == j["pk"]
            )

            if "favorite_feed_entries" not in user_json["fields"]:
                user_json["fields"]["favorite_feed_entries"] = []

            user_json["fields"]["favorite_feed_entries"].append(
                favorite_feed_entry_user_mapping_json["fields"]["feed_entry"]
            )

        fixture_json = [
            j for j in fixture_json if j["model"] != "api.favoritefeedentryusermapping"
        ]

        email_address_jsons: list[dict[str, Any]] = []
        for user_json in filter((lambda j: j["model"] == "api.user"), fixture_json):
            user_json["fields"]["created_at"] = user_json["fields"]["created_at"] + "Z"
            user_json["fields"]["is_superuser"] = True
            user_json["fields"]["is_staff"] = True
            email_address_jsons.append(
                {
                    "model": "account.emailaddress",
                    "fields": {
                        "user": user_json["pk"],
                        "email": user_json["fields"]["email"],
                        "verified": True,
                        "primary": True,
                    },
                }
            )

        fixture_json.extend(email_address_jsons)

        for verification_token_json in filter(
            (lambda j: j["model"] == "api.verificationtoken"), fixture_json
        ):
            verification_token_json["fields"]["expires_at"] = (
                verification_token_json["fields"]["expires_at"] + "Z"
            )

        for feed_json in filter((lambda j: j["model"] == "api.feed"), fixture_json):
            feed_json["fields"]["published_at"] = (
                feed_json["fields"]["published_at"] + "Z"
            )
            if feed_json["fields"]["updated_at"] is not None:
                feed_json["fields"]["updated_at"] = (
                    feed_json["fields"]["updated_at"] + "Z"
                )

            feed_json["fields"]["update_backoff_until"] = (
                feed_json["fields"]["update_backoff_until"] + "Z"
            )

            feed_json["fields"]["db_created_at"] = (
                feed_json["fields"]["db_created_at"] + "Z"
            )
            feed_json["fields"]["db_updated_at"] = (
                feed_json["fields"]["db_updated_at"] + "Z"
            )

        for feed_entry_json in filter(
            (lambda j: j["model"] == "api.feedentry"), fixture_json
        ):
            feed_entry_json["fields"]["published_at"] = (
                feed_entry_json["fields"]["published_at"] + "Z"
            )
            if feed_entry_json["fields"]["updated_at"] is not None:
                feed_entry_json["fields"]["updated_at"] = (
                    feed_entry_json["fields"]["updated_at"] + "Z"
                )

            feed_entry_json["fields"]["db_created_at"] = (
                feed_entry_json["fields"]["db_created_at"] + "Z"
            )

        for read_feed_entry_user_mapping_json in filter(
            (lambda j: j["model"] == "api.readfeedentryusermapping"), fixture_json
        ):
            read_feed_entry_user_mapping_json["fields"]["read_at"] = (
                read_feed_entry_user_mapping_json["fields"]["read_at"] + "Z"
            )

        with open(options["to_filepath"], "w") as f:
            ujson.dump(fixture_json, f, indent=2, ensure_ascii=False)
