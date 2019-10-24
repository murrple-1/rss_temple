import re

from api.exceptions import QueryException


class _DefaultDescriptor:
    def __init__(self, sort_key, direction):
        if type(sort_key) is not int:
            raise TypeError('sort_key must be int')

        if direction not in ['ASC', 'DESC']:
            raise ValueError('direction not recognized')

        self.sort_key = sort_key
        self.direction = direction


class _SortConfig:
    def __init__(self, field_names, default_descriptor):
        if type(field_names) is not list:
            raise TypeError('field_names must be list')

        if len(field_names) < 1:
            raise ValueError('field_names must not be empty')

        for field_name in field_names:
            if type(field_name) is not str:
                raise TypeError('field_names element must be str')

        if default_descriptor is not None and type(default_descriptor) is not _DefaultDescriptor:
            raise TypeError(
                'default_descriptor must be None or _DefaultDescriptor')

        self.field_names = field_names
        self.default_descriptor = default_descriptor


_sort_configs = {
    'user': {
        'uuid': _SortConfig(['uuid'], _DefaultDescriptor(0, 'ASC')),
        'email': _SortConfig(['email'], None),
    },
    'usercategory': {
        'uuid': _SortConfig(['uuid'], _DefaultDescriptor(0, 'ASC')),
        'text': _SortConfig(['text'], None),
    },
    'feed': {
        'uuid': _SortConfig(['uuid'], _DefaultDescriptor(0, 'ASC')),
        'title': _SortConfig(['title'], None),
        'feedUrl': _SortConfig(['feed_url'], None),
        'homeUrl': _SortConfig(['home_url'], None),
        'publishedAt': _SortConfig(['published_at'], None),
        'updatedAt': _SortConfig(['updated_at'], None),

        'subscribed': _SortConfig(['is_subscribed'], None),
        'customTitle': _SortConfig(['custom_title'], None),
        'calculatedTitle': _SortConfig(['custom_title', 'title'], None),
    },
    'feedentry': {
        'uuid': _SortConfig(['uuid'], _DefaultDescriptor(0, 'ASC')),
        'createdAt': _SortConfig(['created_at'], None),
        'publishedAt': _SortConfig(['published_at'], None),
        'updatedAt': _SortConfig(['created_at'], None),
        'title': _SortConfig(['title'], None),
    },
}

__sort_regex = re.compile(r'^([A-Z0-9_]+):(ASC|DESC)$', re.IGNORECASE)


def to_sort_list(object_name, sort, default_sort_enabled):
    sort_list = []

    if sort:
        sort_parts = sort.split(',')
        for sort_part in sort_parts:
            match = __sort_regex.search(sort_part)
            if match:
                field_name = match.group(1)
                direction = match.group(2)

                sort_list.append({
                    'field_name': field_name,
                    'direction': direction,
                })
            else:
                raise QueryException('\'sort\' malformed', 400)

    if default_sort_enabled:
        default_sort_list = _to_default_sort_list(object_name)

        sort_field_names = frozenset(
            sort['field_name'].lower() for sort in sort_list)

        for default_sort in default_sort_list:
            if default_sort['field_name'].lower() not in sort_field_names:
                sort_list.append(default_sort)

    return sort_list


def _to_default_sort_list(object_name):
    object_sort_configs = _sort_configs[object_name]

    field_name_dict = {}
    for field_name, object_sort_config in object_sort_configs.items():
        if object_sort_config.default_descriptor is not None:
            if object_sort_config.default_descriptor.sort_key not in field_name_dict:
                field_name_dict[object_sort_config.default_descriptor.sort_key] = [
                ]

            field_name_dict[object_sort_config.default_descriptor.sort_key].append({
                'field_name': field_name,
                'direction': object_sort_config.default_descriptor.direction,
            })

    sort_list = []
    for sort_key in sorted(field_name_dict.keys()):
        sort_list.extend(field_name_dict[sort_key])

    return sort_list


def sort_list_to_db_sort_list(object_name, sort_list):
    db_sort_list = []
    for sort_desc in sort_list:
        field_name = sort_desc['field_name']
        direction = sort_desc['direction']
        db_sort_field_names = _to_db_sort_field_names(object_name, field_name)
        if db_sort_field_names:
            for db_sort_field_name in db_sort_field_names:
                db_sort_list.append({
                    'field_name': db_sort_field_name,
                    'direction': direction,
                })
        else:
            raise QueryException(
                f'\'{field_name}\' field not recognized for \'sort\'', 400)

    return db_sort_list


def _to_db_sort_field_names(object_name, field_name):
    field_name = field_name.lower()

    object_sort_configs = _sort_configs[object_name]

    for _field_name, object_sort_config in object_sort_configs.items():
        if field_name == _field_name.lower():
            return object_sort_config.field_names

    return None


def to_order_by_fields(sort_list):
    order_by_fields = []

    for sort_desc in sort_list:
        field_name = sort_desc['field_name']
        direction = sort_desc['direction']

        order_by_direction = '-' if direction.upper() == 'DESC' else ''

        order_by_fields.append(f'{order_by_direction}{field_name}')

    return order_by_fields
