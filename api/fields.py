from typing import Any, Callable, TypedDict

from django.http import HttpRequest


class _FieldConfig:
    def __init__(self, accessor: Callable[[HttpRequest, Any], Any], default: bool):
        self.accessor = accessor
        self.default = default


def _feedentry_readAt(request: HttpRequest, db_obj: Any):
    read_mapping = db_obj.read_mapping(request.user)
    if read_mapping is not None:
        return read_mapping.read_at.isoformat()
    else:
        return None


_field_configs: dict[str, dict[str, _FieldConfig]] = {
    "user": {
        "uuid": _FieldConfig(lambda request, db_obj: str(db_obj.uuid), True),
        "email": _FieldConfig(lambda request, db_obj: db_obj.email, False),
        "subscribedFeedUuids": _FieldConfig(
            lambda request, db_obj: [
                str(key) for key in db_obj.subscribed_feeds_dict().keys()
            ],
            False,
        ),
        "attributes": _FieldConfig(lambda request, db_obj: db_obj.attributes, False),
        "hasGoogleLogin": _FieldConfig(
            lambda request, db_obj: db_obj.google_login() is not None, False
        ),
        "hasFacebookLogin": _FieldConfig(
            lambda request, db_obj: db_obj.facebook_login() is not None, False
        ),
    },
    "usercategory": {
        "uuid": _FieldConfig(lambda request, db_obj: str(db_obj.uuid), True),
        "text": _FieldConfig(lambda request, db_obj: db_obj.text, True),
        "feedUuids": _FieldConfig(
            lambda request, db_obj: [str(feed.uuid) for feed in db_obj.feeds()], False
        ),
    },
    "feed": {
        "uuid": _FieldConfig(lambda request, db_obj: str(db_obj.uuid), True),
        "title": _FieldConfig(lambda request, db_obj: db_obj.title, False),
        "feedUrl": _FieldConfig(lambda request, db_obj: db_obj.feed_url, False),
        "homeUrl": _FieldConfig(lambda request, db_obj: db_obj.home_url, False),
        "publishedAt": _FieldConfig(
            lambda request, db_obj: db_obj.published_at.isoformat(), False
        ),
        "updatedAt": _FieldConfig(
            lambda request, db_obj: db_obj.updated_at.isoformat()
            if db_obj.updated_at is not None
            else None,
            False,
        ),
        "subscribed": _FieldConfig(lambda request, db_obj: db_obj.is_subscribed, False),
        "customTitle": _FieldConfig(lambda request, db_obj: db_obj.custom_title, False),
        "calculatedTitle": _FieldConfig(
            lambda request, db_obj: db_obj.custom_title
            if db_obj.custom_title is not None
            else db_obj.title,
            False,
        ),
        "userCategoryUuids": _FieldConfig(
            lambda request, db_obj: [
                str(user_category.uuid)
                for user_category in db_obj.user_categories(request.user)
            ],
            False,
        ),
        "readCount": _FieldConfig(
            lambda request, db_obj: db_obj.read_count(request.user), False
        ),
        "unreadCount": _FieldConfig(
            lambda request, db_obj: db_obj.unread_count(request.user), False
        ),
    },
    "feedentry": {
        "uuid": _FieldConfig(lambda request, db_obj: str(db_obj.uuid), True),
        "id": _FieldConfig(lambda request, db_obj: db_obj.id, False),
        "createdAt": _FieldConfig(
            lambda request, db_obj: db_obj.created_at.isoformat()
            if db_obj.created_at is not None
            else None,
            False,
        ),
        "publishedAt": _FieldConfig(
            lambda request, db_obj: db_obj.published_at.isoformat(), False
        ),
        "updatedAt": _FieldConfig(
            lambda request, db_obj: db_obj.updated_at.isoformat()
            if db_obj.updated_at is not None
            else None,
            False,
        ),
        "title": _FieldConfig(lambda request, db_obj: db_obj.title, False),
        "url": _FieldConfig(lambda request, db_obj: db_obj.url, False),
        "content": _FieldConfig(lambda request, db_obj: db_obj.content, False),
        "authorName": _FieldConfig(lambda request, db_obj: db_obj.author_name, False),
        "feedUuid": _FieldConfig(lambda request, db_obj: str(db_obj.feed_id), False),
        "fromSubscription": _FieldConfig(
            lambda request, db_obj: db_obj.from_subscription(request.user),
            False,
        ),
        "isRead": _FieldConfig(
            lambda request, db_obj: db_obj.is_read(request.user), False
        ),
        "isFavorite": _FieldConfig(
            lambda request, db_obj: db_obj.is_favorite(request.user), False
        ),
        "readAt": _FieldConfig(_feedentry_readAt, False),
    },
}


class FieldMap(TypedDict):
    field_name: str
    accessor: Callable[[HttpRequest, Any], Any]


def get_default_field_maps(object_name: str):
    object_field_configs = _field_configs[object_name]
    default_field_maps: list[FieldMap] = []

    for field_name, field_config in object_field_configs.items():
        if field_config.default:
            default_field_map: FieldMap = {
                "field_name": field_name,
                "accessor": field_config.accessor,
            }

            default_field_maps.append(default_field_map)

    return default_field_maps


def get_all_field_maps(object_name: str):
    object_field_configs = _field_configs[object_name]
    all_field_maps: list[FieldMap] = []

    for field_name, field_config in object_field_configs.items():
        field_map: FieldMap = {
            "field_name": field_name,
            "accessor": field_config.accessor,
        }

        all_field_maps.append(field_map)

    return all_field_maps


def to_field_map(object_name: str, field_name: str) -> FieldMap | None:
    object_field_configs = _field_configs[object_name]

    for _field_name, field_config in object_field_configs.items():
        if field_name.lower() == _field_name.lower():
            return {
                "field_name": _field_name,
                "accessor": field_config.accessor,
            }
    return None


def field_list(object_name: str):
    return _field_configs[object_name].keys()
