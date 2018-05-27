class _FieldConfig:
    def __init__(self, accessor, default):
        if not callable(accessor):
            raise TypeError('accessor must be callable')

        if not isinstance(default, bool):
            raise TypeError('default must be bool')

        self.accessor = accessor
        self.default = default


__field_configs = {
    'user': {
        'uuid': _FieldConfig(lambda context, db_obj: str(db_obj.uuid), True),
        'email': _FieldConfig(lambda context, db_obj: db_obj.email, False),
        'subscribedFeedUuids': _FieldConfig(lambda context, db_obj: (str(_uuid) for _uuid in db_obj.subscribed_feeds().values_list('uuid', flat=True)), False),
    },
    'feed': {
        'uuid': _FieldConfig(lambda context, db_obj: str(db_obj.uuid), True),
        'title': _FieldConfig(lambda context, db_obj: db_obj.title, False),
        'feedUrl': _FieldConfig(lambda context, db_obj: db_obj.feed_url, False),
        'homeUrl': _FieldConfig(lambda context, db_obj: db_obj.home_url, False),
        'publishedAt': _FieldConfig(lambda context, db_obj: context.format_datetime(db_obj.published_at), False),
        'updatedAt': _FieldConfig(lambda context, db_obj: context.format_datetime(db_obj.updated_at) if db_obj.updated_at is not None else None, False),
    },
}


def get_default_field_maps(object_name):
    object_field_configs = __field_configs[object_name]
    default_field_maps = []

    for field_name, field_config in object_field_configs.items():
        if field_config.default:
            default_field_map = {
                'field_name': field_name,
                'accessor': field_config.accessor,
            }

            default_field_maps.append(default_field_map)

    return default_field_maps


def get_all_field_maps(object_name):
    object_field_configs = __field_configs[object_name]
    all_field_maps = []

    for field_name, field_config in object_field_configs.items():
        field_map = {
            'field_name': field_name,
            'accessor': field_config.accessor,
        }

        all_field_maps.append(field_map)

    return all_field_maps


def to_field_map(object_name, field_name):
    object_field_configs = __field_configs[object_name]

    for _field_name, field_config in object_field_configs.items():
        if field_name.lower() == _field_name.lower():
            return {
                'field_name': _field_name,
                'accessor': field_config.accessor,
            }
    return None

def field_list(object_name):
    return __field_configs[object_name].keys()
