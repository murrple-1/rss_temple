class _FieldConfig:
    def __init__(self, accessor, default):
        if not callable(accessor):
            raise TypeError('accessor must be callable')

        if not isinstance(default, bool):
            raise TypeError('default must be bool')

        self.accessor = accessor
        self.default = default


def _feed_calculatedTitle(context, db_obj):
    custom_title = db_obj.custom_title(context.request.user)
    return custom_title if custom_title is not None else db_obj.title


__field_configs = {
    'user': {
        'uuid': _FieldConfig(lambda context, db_obj: str(db_obj.uuid), True),
        'email': _FieldConfig(lambda context, db_obj: db_obj.email, False),
        'subscribedFeedUuids': _FieldConfig(lambda context, db_obj: (str(feed.uuid) for feed in db_obj.subscribed_feeds()), False),
    },
    'usercategory': {
        'uuid': _FieldConfig(lambda context, db_obj: str(db_obj.uuid), True),
        'text': _FieldConfig(lambda context, db_obj: db_obj.text, True),
    },
    'feed': {
        'uuid': _FieldConfig(lambda context, db_obj: str(db_obj.uuid), True),
        'title': _FieldConfig(lambda context, db_obj: db_obj.title, False),
        'feedUrl': _FieldConfig(lambda context, db_obj: db_obj.feed_url, False),
        'homeUrl': _FieldConfig(lambda context, db_obj: db_obj.home_url, False),
        'publishedAt': _FieldConfig(lambda context, db_obj: context.format_datetime(db_obj.published_at), False),
        'updatedAt': _FieldConfig(lambda context, db_obj: context.format_datetime(db_obj.updated_at) if db_obj.updated_at is not None else None, False),

        'subscribed': _FieldConfig(lambda context, db_obj: db_obj.subscribed(context.request.user), False),
        'customTitle': _FieldConfig(lambda context, db_obj: db_obj.custom_title(context.request.user), False),
        'calculatedTitle': _FieldConfig(_feed_calculatedTitle, False),
    },
    'feedentry': {
        'uuid': _FieldConfig(lambda context, db_obj: str(db_obj.uuid), True),
        'id': _FieldConfig(lambda context, db_obj: db_obj.id, False),
        'createdAt': _FieldConfig(lambda context, db_obj: context.format_datetime(db_obj.created_at) if db_obj.created_at is not None else None, False),
        'publishedAt': _FieldConfig(lambda context, db_obj: context.format_datetime(db_obj.published_at), False),
        'updatedAt': _FieldConfig(lambda context, db_obj: context.format_datetime(db_obj.updated_at) if db_obj.updated_at is not None else None, False),
        'title': _FieldConfig(lambda context, db_obj: db_obj.title, False),
        'url': _FieldConfig(lambda context, db_obj: db_obj.url, False),
        'content': _FieldConfig(lambda context, db_obj: db_obj.content, False),
        'authorName': _FieldConfig(lambda context, db_obj: db_obj.author_name, False),

        'fromSubscription': _FieldConfig(lambda context, db_obj: db_obj.from_subscription(context.request.user), False),
        'isRead': _FieldConfig(lambda context, db_obj: db_obj.is_read(context.request.user), False),
        'isFavorite': _FieldConfig(lambda context, db_obj: db_obj.is_favorite(context.request.user), False),
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
