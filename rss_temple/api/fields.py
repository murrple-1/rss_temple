class _FieldConfig:
    def __init__(self, accessor, default):
        if not callable(accessor):
            raise TypeError('accessor must be callable')

        if type(default) is not bool:
            raise TypeError('default must be bool')

        self.accessor = accessor
        self.default = default


def _feedentry_readAt(context, db_obj):
    read_mapping = db_obj.read_mapping(context.request.user)
    if read_mapping is not None:
        return context.format_datetime(read_mapping.read_at)
    else:
        return None


_field_configs = {
    'user': {
        'uuid': _FieldConfig(lambda context, db_obj: str(db_obj.uuid), True),
        'email': _FieldConfig(lambda context, db_obj: db_obj.email, False),
        'subscribedFeedUuids': _FieldConfig(lambda context, db_obj: [str(key) for key in db_obj.subscribed_feeds_dict().keys()], False),
        'attributes': _FieldConfig(lambda context, db_obj: db_obj.attributes, False),

        'hasGoogleLogin': _FieldConfig(lambda context, db_obj: db_obj.google_login() is not None, False),
        'hasFacebookLogin': _FieldConfig(lambda context, db_obj: db_obj.facebook_login() is not None, False),
    },
    'usercategory': {
        'uuid': _FieldConfig(lambda context, db_obj: str(db_obj.uuid), True),
        'text': _FieldConfig(lambda context, db_obj: db_obj.text, True),
        'feedUuids': _FieldConfig(lambda context, db_obj: [str(feed.uuid) for feed in db_obj.feeds()], False),
    },
    'feed': {
        'uuid': _FieldConfig(lambda context, db_obj: str(db_obj.uuid), True),
        'title': _FieldConfig(lambda context, db_obj: db_obj.title, False),
        'feedUrl': _FieldConfig(lambda context, db_obj: db_obj.feed_url, False),
        'homeUrl': _FieldConfig(lambda context, db_obj: db_obj.home_url, False),
        'publishedAt': _FieldConfig(lambda context, db_obj: context.format_datetime(db_obj.published_at), False),
        'updatedAt': _FieldConfig(lambda context, db_obj: context.format_datetime(db_obj.updated_at) if db_obj.updated_at is not None else None, False),

        'subscribed': _FieldConfig(lambda context, db_obj: db_obj.is_subscribed, False),
        'customTitle': _FieldConfig(lambda context, db_obj: db_obj.custom_title, False),
        'calculatedTitle': _FieldConfig(lambda context, db_obj: db_obj.custom_title if db_obj.custom_title is not None else db_obj.title, False),
        'userCategoryUuids': _FieldConfig(lambda context, db_obj: [str(user_category.uuid) for user_category in db_obj.user_categories(context.request.user)], False),
        'readCount': _FieldConfig(lambda context, db_obj: db_obj.read_count(context.request.user), False),
        'unreadCount': _FieldConfig(lambda context, db_obj: db_obj.unread_count(context.request.user), False),
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
        'feedUuid': _FieldConfig(lambda context, db_obj: str(db_obj.feed_id), False),

        'fromSubscription': _FieldConfig(lambda context, db_obj: db_obj.from_subscription(context.request.user), False),
        'isRead': _FieldConfig(lambda context, db_obj: db_obj.is_read(context.request.user), False),
        'isFavorite': _FieldConfig(lambda context, db_obj: db_obj.is_favorite(context.request.user), False),
        'readAt': _FieldConfig(_feedentry_readAt, False),
    },
}


def get_default_field_maps(object_name):
    object_field_configs = _field_configs[object_name]
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
    object_field_configs = _field_configs[object_name]
    all_field_maps = []

    for field_name, field_config in object_field_configs.items():
        field_map = {
            'field_name': field_name,
            'accessor': field_config.accessor,
        }

        all_field_maps.append(field_map)

    return all_field_maps


def to_field_map(object_name, field_name):
    object_field_configs = _field_configs[object_name]

    for _field_name, field_config in object_field_configs.items():
        if field_name.lower() == _field_name.lower():
            return {
                'field_name': _field_name,
                'accessor': field_config.accessor,
            }
    return None


def field_list(object_name):
    return _field_configs[object_name].keys()
