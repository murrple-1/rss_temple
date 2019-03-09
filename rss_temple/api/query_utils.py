from django.conf import settings

import ujson

from api import fields as fieldutils, searches as searchutils, sorts as sortutils
from api.exceptions import QueryException


def serialize_content(obj):
    content = ujson.dumps(obj)
    return content, 'application/json'


_DEFAULT_COUNT = settings.DEFAULT_COUNT
_MAX_COUNT = settings.MAX_COUNT


def get_count(
        _json,
        default=_DEFAULT_COUNT,
        max_=_MAX_COUNT,
        param_name='count'):
    if param_name not in _json:
        return default

    count = _json[param_name]

    if not isinstance(count, int):
        raise QueryException('\'{0}\' must be int'.format(param_name), 400)

    if count < 0:
        raise QueryException(
            '\'{0}\' must be greater than or equal to 0'.format(param_name), 400)
    elif count > max_:
        raise QueryException(
            '\'{0}\' must be less than or equal to {1}'.format(param_name, max_), 400)

    return count


_DEFAULT_SKIP = settings.DEFAULT_SKIP


def get_skip(_json, default=_DEFAULT_SKIP, param_name='skip'):
    if param_name not in _json:
        return default

    skip = _json[param_name]

    if not isinstance(skip, int):
        raise QueryException('\'{0}\' must be int'.format(param_name), 400)

    if skip < 0:
        raise QueryException(
            '\'{0}\' must be greater than 0'.format(param_name), 400)

    return skip


_DEFAULT_RETURN_OBJECTS = settings.DEFAULT_RETURN_OBJECTS


def get_return_objects(
        _json,
        default=_DEFAULT_RETURN_OBJECTS,
        param_name='objects'):
    if param_name not in _json:
        return default

    return_objects = _json[param_name]

    if not isinstance(return_objects, bool):
        raise QueryException('\'{0}\' must be boolean'.format(param_name), 400)  # pragma: no cover

    return return_objects


_DEFAULT_RETURN_TOTAL_COUNT = settings.DEFAULT_RETURN_TOTAL_COUNT


def get_return_total_count(
        _json,
        default=_DEFAULT_RETURN_TOTAL_COUNT,
        param_name='totalCount'):
    if param_name not in _json:
        return default

    return_total_count = _json[param_name]

    if not isinstance(return_total_count, bool):
        raise QueryException('\'{0}\' must be boolean'.format(param_name), 400)  # pragma: no cover

    return return_total_count


def get_sort(_json, object_name, param_name='sort',
             disable_default_sort_param_name='disableDefaultSort'):
    sort = None
    if param_name in _json:
        sort = _json[param_name]

        if sort is not None:
            if not isinstance(sort, str):
                raise QueryException('\'{0}\' must be null or string', 400)  # pragma: no cover

    default_sort_enabled = True
    if disable_default_sort_param_name in _json:
        if not isinstance(_json[disable_default_sort_param_name], bool):
            raise QueryException('\'{0}\' must be boolean'.format(disable_default_sort_param_name), 400)  # pragma: no cover

        default_sort_enabled = not _json[disable_default_sort_param_name]

    sort_list = sortutils.to_sort_list(object_name, sort, default_sort_enabled)
    db_sort_list = sortutils.sort_list_to_db_sort_list(object_name, sort_list)

    sort = sortutils.to_order_by_fields(db_sort_list)
    return sort


def get_search(context, _json, object_name, param_name='search'):
    if param_name not in _json:
        return []

    search = _json[param_name]

    if not isinstance(search, str):
        raise QueryException('\'{0}\' must be string'.format(param_name), 400)  # pragma: no cover

    filter_args = searchutils.to_filter_args(object_name, context, search)
    return filter_args


def get_fields__query_dict(query_dict, param_name='fields'):
    fields = query_dict.get(param_name, None)

    if not fields:
        return []

    return fields.split(',')


def get_fields__json(_json, param_name='fields'):
    if param_name not in _json:
        return []

    fields = _json[param_name]

    if not isinstance(fields, list):
        raise QueryException('\'{0}\' must be array'.format(param_name), 400)  # pragma: no cover

    for field in fields:
        if not isinstance(field, str):
            raise QueryException(
                '\'{0}\' element must be string'.format(param_name), 400)  # pragma: no cover

    return fields


def get_field_maps(fields, object_name, param_name='fields'):
    if settings.DEBUG and len(fields) == 1 and fields[0] == '_all':
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


def generate_return_object(field_maps, db_obj, context):
    return_obj = {}
    for field_map in field_maps:
        field_name = field_map['field_name']
        return_obj[field_name] = field_map['accessor'](context, db_obj)

    return return_obj
