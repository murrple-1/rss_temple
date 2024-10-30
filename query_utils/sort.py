import re
from dataclasses import dataclass
from typing import Callable, Literal, TypedDict, cast

from django.db.models import F, OrderBy


@dataclass(slots=True)
class DefaultDescriptor:
    sort_key: int
    direction: Literal["ASC", "DESC"]


@dataclass(slots=True)
class SortConfig:
    field_accessor_fns: list[Callable[[str], OrderBy]]
    default_descriptor: DefaultDescriptor | None


def standard_sort(field_name: str):
    f = F(field_name)
    return lambda dir_: f.desc() if dir_.upper() == "DESC" else f.asc()


_sort_regex = re.compile(r"^([A-Z0-9_]+):(ASC|DESC)$", re.IGNORECASE)


class _SortConfigDict(TypedDict):
    field_name: str
    direction: Literal["ASC", "DESC"]


def to_sort_list(
    object_name: str,
    sort: str | None,
    default_sort_enabled: bool,
    sort_configs: dict[str, dict[str, SortConfig]],
):
    sort_list: list[_SortConfigDict] = []

    if sort:
        sort_parts = sort.split(",")
        for sort_part in sort_parts:
            match = _sort_regex.search(sort_part)
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
                raise ValueError("sort malformed")

    if default_sort_enabled:
        default_sort_list = _to_default_sort_list(object_name, sort_configs)

        sort_field_names = frozenset(sort["field_name"].lower() for sort in sort_list)

        for default_sort in default_sort_list:
            if default_sort["field_name"].lower() not in sort_field_names:
                sort_list.append(default_sort)

    return sort_list


def _to_default_sort_list(
    object_name: str, sort_configs: dict[str, dict[str, SortConfig]]
) -> list[_SortConfigDict]:
    object_sort_configs = sort_configs[object_name]

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


def sort_list_to_order_by_args(
    object_name: str,
    sort_list: list[_SortConfigDict],
    sort_configs: dict[str, dict[str, SortConfig]],
):
    db_sort_list: list[OrderBy] = []
    for sort_desc in sort_list:
        field_name = sort_desc["field_name"]
        direction = sort_desc["direction"]
        db_sort_field_accessor_fns = _to_db_sort_field_accessor_fns(
            object_name, field_name, sort_configs
        )
        if db_sort_field_accessor_fns:
            for db_sort_field_accessor_fn in db_sort_field_accessor_fns:
                db_sort_list.append(db_sort_field_accessor_fn(direction))
        else:
            raise AttributeError(field_name)

    return db_sort_list


def _to_db_sort_field_accessor_fns(
    object_name: str, field_name: str, sort_configs: dict[str, dict[str, SortConfig]]
):
    field_name = field_name.lower()

    object_sort_configs = sort_configs[object_name]

    for _field_name, object_sort_config in object_sort_configs.items():
        if field_name == _field_name.lower():
            return object_sort_config.field_accessor_fns

    return None
