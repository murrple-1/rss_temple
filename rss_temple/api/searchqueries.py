import timeit
import logging

from django.conf import settings

import ujson

from . import authenticate, fields as fieldutils, searches as searchutils, sorts as sortutils
from .exceptions import QueryException


class Context:
    def __init__(self):
        self.datetime_format = getattr(settings, 'DEFAULT_DATETIME_FORMAT', '%Y-%m-%d %H:%M:%S')
        self.date_format = getattr(settings, 'DEFAULT_DATE_FORMAT', '%Y-%m-%d')
        self.time_format = getattr(settings, 'DEFAULT_TIME_FORMAT', '%H:%M:%S')


    def parse_query_dict(self, query_dict):
        dt_format = query_dict.get('_dtformat', None)
        if dt_format is not None:
            self.datetime_format = dt_format

        d_format = query_dict.get('_dformat', None)
        if d_format is not None:
            self.date_format = d_format

        t_format = query_dict.get('_tformat', None)
        if t_format is not None:
            self.time_format = t_format

    def format_datetime(self, datetime):
        return datetime.strftime(self.datetime_format)


    def format_date(self, date):
        return date.strftime(self.date_format)


    def format_time(self, time):
        return time.strftime(self.time_format)


    def format_decimal(self, decimal):
        return float(decimal)


_metrics_logger = logging.getLogger('metrics')
def serialize_content(obj):
    content = None
    if _metrics_logger.isEnabledFor(logging.DEBUG):
        start_time = timeit.default_timer()
        content = ujson.dumps(obj)
        end_time = timeit.default_timer()

        _metrics_logger.debug(
            'dumps (JSON): %s ms for %s chars',
            (end_time - start_time) * 1000,
            len(content))
    else:
        content = ujson.dumps(obj)

    return content, 'application/json'


_DEFAULT_COUNT = settings.DEFAULT_COUNT
_MAX_COUNT = settings.MAX_COUNT


def get_count(
        query_dict,
        default=_DEFAULT_COUNT,
        max=_MAX_COUNT,
        param_name='count'):
    count = query_dict.get(param_name, None)
    if not count:
        return default

    try:
        count = int(count)
    except ValueError:
        raise QueryException('\'count\' must be int', 400)

    if count < 0:
        raise QueryException(
            '\'count\' must be greater than or equal to 0', 400)
    elif count > max:
        raise QueryException(
            '\'count\' must be less than or equal to {0}'.format(max), 400)

    return count


_DEFAULT_SKIP = settings.DEFAULT_SKIP


def get_skip(query_dict, default=_DEFAULT_SKIP, param_name='skip'):
    skip = query_dict.get(param_name, None)
    if not skip:
        return default

    try:
        skip = int(skip)
    except ValueError:
        raise QueryException('\'skip\' must be int', 400)

    if skip < 0:
        raise QueryException('\'skip\' must be greater than 0', 400)

    return skip


_DEFAULT_RETURN_OBJECTS = settings.DEFAULT_RETURN_OBJECTS


def get_return_objects(
        query_dict,
        default=_DEFAULT_RETURN_OBJECTS,
        param_name='objects'):
    return_objects = query_dict.get(param_name, None)
    if not return_objects:
        return default

    return_objects = return_objects.lower() == 'true'
    return return_objects


_DEFAULT_RETURN_TOTAL_COUNT = settings.DEFAULT_RETURN_TOTAL_COUNT


def get_return_total_count(
        query_dict,
        default=_DEFAULT_RETURN_TOTAL_COUNT,
        param_name='totalcount'):
    return_total_count = query_dict.get(
        param_name, None)
    if not return_total_count:
        return default

    return_total_count = return_total_count.lower() == 'true'
    return return_total_count


def get_sort(query_dict, object_name, param_name='sort',
             disable_default_sort_aram_name='_disabledefaultsort'):
    sort = query_dict.get(param_name, None)

    default_sort_enabled = query_dict.get(
        disable_default_sort_aram_name, None) != 'true'

    sort_list = sortutils.to_sort_list(object_name, sort, default_sort_enabled)
    db_sort_list = sortutils.sort_list_to_db_sort_list(object_name, sort_list)

    sort = sortutils.to_order_by_fields(db_sort_list)
    return sort


def get_search(query_dict, object_name, param_name='search'):
    search = query_dict.get(param_name, None)
    if not search:
        return []

    filter_args = searchutils.to_filter_args(object_name, search)
    return filter_args


def get_field_maps(query_dict, object_name, param_name='fields'):
    fields = query_dict.get(param_name, None)
    if not fields:
        return fieldutils.get_default_field_maps(object_name)

    if fields == '_all' and settings.DEBUG:
        field_maps = fieldutils.get_all_field_maps(object_name)
    else:
        fields = fields.split(',')

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
