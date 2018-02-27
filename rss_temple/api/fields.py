__field_configs = {

    'user': {
        'uuid': {
            'accessor': lambda context, db_obj: str(db_obj.uuid),
            'default': True,
        },
        'email': {
            'accessor': lambda context, db_obj: db_obj.email,
            'default': False,
        },
    },
}


def get_default_field_maps(object_name):
    object_field_configs = __field_configs[object_name]
    default_field_maps = []

    for field_name, field_config in object_field_configs.items():
        if 'default' in field_config and field_config['default'] is True:
            default_field_map = {
                'field_name': field_name,
                'accessor': field_config['accessor'],
            }

            default_field_maps.append(default_field_map)

    return default_field_maps


def get_all_field_maps(object_name):
    object_field_configs = __field_configs[object_name]
    all_field_maps = []

    for field_name, field_config in object_field_configs.items():
        field_map = {
            'field_name': field_name,
            'accessor': field_config['accessor'],
        }

        all_field_maps.append(field_map)

    return all_field_maps


def to_field_map(object_name, field_name):
    object_field_configs = __field_configs[object_name]

    for _field_name, field_config in object_field_configs.items():
        if field_name.lower() == _field_name.lower():
            return {
                'field_name': _field_name,
                'accessor': field_config['accessor'],
            }
    return None
