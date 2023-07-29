import re
from typing import Callable, Literal, TypedDict, cast

from django.db.models import F, OrderBy

from api.exceptions import QueryException


class _DefaultDescriptor:
    direction: Literal["ASC", "DESC"]

    def __init__(self, sort_key: int, direction: Literal["ASC", "DESC"]):
        self.sort_key = sort_key
        self.direction = direction


class _SortConfig:
    def __init__(
        self,
        field_accessor_fns: list[Callable[[str], OrderBy]],
        default_descriptor: _DefaultDescriptor | None,
    ):
        self.field_accessor_fns = field_accessor_fns
        self.default_descriptor = default_descriptor


def _standard_sort(field_name: str):
    f = F(field_name)
    return lambda dir_: f.desc() if dir_.upper() == "DESC" else f.asc()


_sort_configs: dict[str, dict[str, _SortConfig]] = {
    "usercategory": {
        "uuid": _SortConfig([_standard_sort("uuid")], _DefaultDescriptor(0, "ASC")),
        "text": _SortConfig([_standard_sort("text")], None),
    },
    "feed": {
        "uuid": _SortConfig([_standard_sort("uuid")], _DefaultDescriptor(0, "ASC")),
        "title": _SortConfig([_standard_sort("title")], None),
        "feedUrl": _SortConfig([_standard_sort("feed_url")], None),
        "homeUrl": _SortConfig([_standard_sort("home_url")], None),
        "publishedAt": _SortConfig([_standard_sort("published_at")], None),
        "updatedAt": _SortConfig([_standard_sort("updated_at")], None),
        "subscribed": _SortConfig([_standard_sort("is_subscribed")], None),
        "customTitle": _SortConfig([_standard_sort("custom_title")], None),
        "calculatedTitle": _SortConfig(
            [_standard_sort("custom_title"), _standard_sort("title")], None
        ),
    },
    "feedentry": {
        "uuid": _SortConfig([_standard_sort("uuid")], _DefaultDescriptor(0, "ASC")),
        "createdAt": _SortConfig([_standard_sort("created_at")], None),
        "publishedAt": _SortConfig([_standard_sort("published_at")], None),
        "updatedAt": _SortConfig([_standard_sort("updated_at")], None),
        "title": _SortConfig([_standard_sort("title")], None),
        "isArchived": _SortConfig([_standard_sort("is_archived")], None),
    },
}

__sort_regex = re.compile(r"^([A-Z0-9_]+):(ASC|DESC)$", re.IGNORECASE)


class _SortConfigDict(TypedDict):
    field_name: str
    direction: Literal["ASC", "DESC"]


def to_sort_list(object_name: str, sort: str | None, default_sort_enabled: bool):
    sort_list: list[_SortConfigDict] = []

    if sort:
        sort_parts = sort.split(",")
        for sort_part in sort_parts:
            match = __sort_regex.search(sort_part)
            if match:
                field_name = match.group(1)
                direction = cast(Literal["ASC", "DESC"], match.group(2))

                sort_list.append(
                    {
                        "field_name": field_name,
                        "direction": direction,
                    }
                )
            else:
                raise QueryException("'sort' malformed", 400)

    if default_sort_enabled:
        default_sort_list = _to_default_sort_list(object_name)

        sort_field_names = frozenset(sort["field_name"].lower() for sort in sort_list)

        for default_sort in default_sort_list:
            if default_sort["field_name"].lower() not in sort_field_names:
                sort_list.append(default_sort)

    return sort_list


def _to_default_sort_list(object_name: str) -> list[_SortConfigDict]:
    object_sort_configs = _sort_configs[object_name]

    field_name_dict: dict[int, list[_SortConfigDict]] = {}
    for field_name, object_sort_config in object_sort_configs.items():
        if object_sort_config.default_descriptor is not None:
            if object_sort_config.default_descriptor.sort_key not in field_name_dict:
                field_name_dict[object_sort_config.default_descriptor.sort_key] = []

            field_name_dict[object_sort_config.default_descriptor.sort_key].append(
                {
                    "field_name": field_name,
                    "direction": object_sort_config.default_descriptor.direction,
                }
            )

    sort_list: list[_SortConfigDict] = []
    for sort_key in sorted(field_name_dict.keys()):
        sort_list.extend(field_name_dict[sort_key])

    return sort_list


def sort_list_to_order_by_args(object_name: str, sort_list: list[_SortConfigDict]):
    db_sort_list: list[OrderBy] = []
    for sort_desc in sort_list:
        field_name = sort_desc["field_name"]
        direction = sort_desc["direction"]
        db_sort_field_accessor_fns = _to_db_sort_field_accessor_fns(
            object_name, field_name
        )
        if db_sort_field_accessor_fns:
            for db_sort_field_accessor_fn in db_sort_field_accessor_fns:
                db_sort_list.append(db_sort_field_accessor_fn(direction))
        else:
            raise QueryException(f"'{field_name}' field not recognized for 'sort'", 400)

    return db_sort_list


def _to_db_sort_field_accessor_fns(object_name: str, field_name: str):
    field_name = field_name.lower()

    object_sort_configs = _sort_configs[object_name]

    for _field_name, object_sort_config in object_sort_configs.items():
        if field_name == _field_name.lower():
            return object_sort_config.field_accessor_fns

    return None
