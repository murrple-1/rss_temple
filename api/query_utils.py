import ujson
from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver

from api import fields as fieldutils
from api import searches as searchutils
from api import sorts as sortutils
from api.exceptions import QueryException

_DEFAULT_COUNT = None
_MAX_COUNT = None
_DEFAULT_SKIP = None
_DEFAULT_RETURN_OBJECTS = None
_DEFAULT_RETURN_TOTAL_COUNT = None


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _DEFAULT_COUNT
    global _MAX_COUNT
    global _DEFAULT_SKIP
    global _DEFAULT_RETURN_OBJECTS
    global _DEFAULT_RETURN_TOTAL_COUNT

    _DEFAULT_COUNT = settings.DEFAULT_COUNT
    _MAX_COUNT = settings.MAX_COUNT
    _DEFAULT_SKIP = settings.DEFAULT_SKIP
    _DEFAULT_RETURN_OBJECTS = settings.DEFAULT_RETURN_OBJECTS
    _DEFAULT_RETURN_TOTAL_COUNT = settings.DEFAULT_RETURN_TOTAL_COUNT


_load_global_settings()


def serialize_content(obj):
    content = ujson.dumps(obj)
    return content, "application/json"


def get_count(json_, default=_DEFAULT_COUNT, max_=_MAX_COUNT, param_name="count"):
    if param_name not in json_:
        return default

    count = json_[param_name]

    if type(count) is not int:
        raise QueryException(f"'{param_name}' must be int", 400)

    if count < 0:
        raise QueryException(f"'{param_name}' must be greater than or equal to 0", 400)
    elif count > max_:
        raise QueryException(
            f"'{param_name}' must be less than or equal to {max_}", 400
        )

    return count


def get_skip(json_, default=_DEFAULT_SKIP, param_name="skip"):
    if param_name not in json_:
        return default

    skip = json_[param_name]

    if type(skip) is not int:
        raise QueryException(f"'{param_name}' must be int", 400)

    if skip < 0:
        raise QueryException(f"'{param_name}' must be greater than 0", 400)

    return skip


def get_return_objects(json_, default=_DEFAULT_RETURN_OBJECTS, param_name="objects"):
    if param_name not in json_:
        return default

    return_objects = json_[param_name]

    if type(return_objects) is not bool:
        raise QueryException(f"'{param_name}' must be boolean", 400)  # pragma: no cover

    return return_objects


def get_return_total_count(
    json_, default=_DEFAULT_RETURN_TOTAL_COUNT, param_name="totalCount"
):
    if param_name not in json_:
        return default

    return_total_count = json_[param_name]

    if type(return_total_count) is not bool:
        raise QueryException(f"'{param_name}' must be boolean", 400)  # pragma: no cover

    return return_total_count


def get_sort(
    json_,
    object_name,
    param_name="sort",
    disable_default_sort_param_name="disableDefaultSort",
):
    sort = None
    if param_name in json_:
        sort = json_[param_name]

        if sort is not None:
            if type(sort) is not str:
                raise QueryException(
                    "'{0}' must be null or string", 400
                )  # pragma: no cover

    default_sort_enabled = True
    if disable_default_sort_param_name in json_:
        if type(json_[disable_default_sort_param_name]) is not bool:
            raise QueryException(
                f"'{disable_default_sort_param_name}' must be boolean", 400
            )  # pragma: no cover

        default_sort_enabled = not json_[disable_default_sort_param_name]

    sort_list = sortutils.to_sort_list(object_name, sort, default_sort_enabled)
    order_by_args = sortutils.sort_list_to_order_by_args(object_name, sort_list)

    return order_by_args


def get_search(request, json_, object_name, param_name="search"):
    if param_name not in json_:
        return []

    search = json_[param_name]

    if type(search) is not str:
        raise QueryException(f"'{param_name}' must be string", 400)  # pragma: no cover

    filter_args = searchutils.to_filter_args(object_name, request, search)
    return filter_args


def get_fields__query_dict(query_dict, param_name="fields"):
    fields = query_dict.get(param_name, None)

    if not fields:
        return []

    return fields.split(",")


def get_fields__json(json_, param_name="fields"):
    if param_name not in json_:
        return []

    fields = json_[param_name]

    if type(fields) is not list:
        raise QueryException(f"'{param_name}' must be array", 400)  # pragma: no cover

    for field in fields:
        if type(field) is not str:
            raise QueryException(
                f"'{param_name}' element must be string", 400
            )  # pragma: no cover

    return fields


def get_field_maps(fields, object_name, param_name="fields"):
    if settings.DEBUG and len(fields) == 1 and fields[0] == "_all":
        field_maps = fieldutils.get_all_field_maps(object_name)
    else:
        field_maps = []
        for field_name in fields:
            field_map = fieldutils.to_field_map(object_name, field_name)
            if field_map:
                field_maps.append(field_map)

        if len(field_maps) < 1:
            field_maps = fieldutils.get_default_field_maps(object_name)

    return field_maps


def generate_return_object(field_maps, db_obj, request):
    return_obj = {}
    for field_map in field_maps:
        field_name = field_map["field_name"]
        return_obj[field_name] = field_map["accessor"](request, db_obj)

    return return_obj
