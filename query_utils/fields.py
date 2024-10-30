from dataclasses import dataclass
from functools import reduce
from typing import AbstractSet, Any, Callable, Iterable, TypedDict

from django.http import HttpRequest


@dataclass(slots=True)
class FieldConfig:
    accessor: Callable[[HttpRequest, Any, Iterable[Any] | None], Any]
    default: bool
    only_fields: AbstractSet[str]


class FieldMap(TypedDict):
    field_name: str
    accessor: Callable[[HttpRequest, Any, Iterable[Any] | None], Any]
    only_fields: AbstractSet[str]


def get_default_field_maps(
    object_name: str, field_configs: dict[str, dict[str, FieldConfig]]
):
    object_field_configs = field_configs[object_name]
    default_field_maps: list[FieldMap] = []

    for field_name, field_config in object_field_configs.items():
        if field_config.default:
            default_field_map: FieldMap = {
                "field_name": field_name,
                "accessor": field_config.accessor,
                "only_fields": field_config.only_fields,
            }

            default_field_maps.append(default_field_map)

    return default_field_maps


def get_all_field_maps(
    object_name: str, field_configs: dict[str, dict[str, FieldConfig]]
):
    object_field_configs = field_configs[object_name]
    all_field_maps: list[FieldMap] = []

    for field_name, field_config in object_field_configs.items():
        field_map: FieldMap = {
            "field_name": field_name,
            "accessor": field_config.accessor,
            "only_fields": field_config.only_fields,
        }

        all_field_maps.append(field_map)

    return all_field_maps


def to_field_map(
    object_name: str, field_name: str, field_configs: dict[str, dict[str, FieldConfig]]
) -> FieldMap | None:
    object_field_configs = field_configs[object_name]

    for _field_name, field_config in object_field_configs.items():
        if field_name.lower() == _field_name.lower():
            return {
                "field_name": _field_name,
                "accessor": field_config.accessor,
                "only_fields": field_config.only_fields,
            }
    return None


def field_list(object_name: str, field_configs: dict[str, dict[str, FieldConfig]]):
    return field_configs[object_name].keys()


def generate_return_object(
    field_maps: list[FieldMap],
    db_obj: Any,
    request: HttpRequest,
    queryset: Iterable[Any] | None,
):
    return_obj: dict[str, Any] = {}
    for field_map in field_maps:
        field_name = field_map["field_name"]
        return_obj[field_name] = field_map["accessor"](request, db_obj, queryset)

    return return_obj


def generate_only_fields(field_maps: list[FieldMap]) -> frozenset[str]:
    return reduce(
        lambda a, b: a.union(b), (fm["only_fields"] for fm in field_maps), frozenset()
    )


def generate_field_names(field_maps: list[FieldMap]) -> frozenset[str]:
    return frozenset(fm["field_name"] for fm in field_maps)
