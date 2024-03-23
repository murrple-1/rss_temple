import datetime
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Collection, TypedDict, cast

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.http import HttpRequest
from django.utils import timezone

from api.models import Feed, FeedEntry, ReadFeedEntryUserMapping, User, UserCategory

_FEED_IS_DEAD_MAX_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _FEED_IS_DEAD_MAX_INTERVAL

    _FEED_IS_DEAD_MAX_INTERVAL = settings.FEED_IS_DEAD_MAX_INTERVAL


_load_global_settings()


@dataclass(slots=True)
class _FieldConfig:
    accessor: Callable[[HttpRequest, Any, Collection[Any] | None], Any]
    default: bool


def _usercategory_feedUuids(
    request: HttpRequest,
    db_obj: UserCategory,
    queryset: Collection[UserCategory] | None,
) -> list[str]:
    if queryset is None:
        return [str(uuid_) for uuid_ in db_obj.feed_uuids]
    else:
        feed_uuids_dict: dict[uuid.UUID, list[uuid.UUID]] | None
        if (
            feed_uuids_dict := getattr(request, "_usercategory_feedUuids", None)
        ) is None:
            feed_uuids_dict = {uc.uuid: [] for uc in queryset}
            for t in UserCategory.feeds.through.objects.filter(
                usercategory_id__in=feed_uuids_dict.keys()
            ):
                feed_uuids_dict[t.usercategory_id].append(t.feed_id)

            setattr(request, "_usercategory_feedUuids", feed_uuids_dict)

        return [str(uuid_) for uuid_ in feed_uuids_dict[db_obj.uuid]]


def _feed_userCategoryUuids(
    request: HttpRequest, db_obj: Feed, queryset: Collection[Feed] | None
) -> list[str]:
    if queryset is None:
        return [
            str(uc.uuid)
            for uc in db_obj.user_categories.filter(user=cast(User, request.user))
        ]
    else:
        user_category_uuids_dict: dict[uuid.UUID, list[uuid.UUID]] | None
        if (
            user_category_uuids_dict := getattr(
                request, "_feed_userCategoryUuids", None
            )
        ) is None:
            user_category_uuids_dict = {f.uuid: [] for f in queryset}
            for t in UserCategory.feeds.through.objects.filter(
                usercategory__user=cast(User, request.user),
                feed_id__in=user_category_uuids_dict.keys(),
            ):
                user_category_uuids_dict[t.feed_id].append(t.usercategory_id)

            setattr(request, "_feed_userCategoryUuids", user_category_uuids_dict)

        return [str(uuid_) for uuid_ in user_category_uuids_dict[db_obj.uuid]]


def _feed__generate_count_lookups(
    request: HttpRequest, queryset: Collection[Feed]
) -> dict[uuid.UUID, Feed._CountsDescriptor]:
    count_lookups: dict[uuid.UUID, Feed._CountsDescriptor] | None = getattr(
        request, "_count_lookups", None
    )
    if count_lookups is None:
        count_lookups = Feed.generate_counts_lookup(
            cast(User, request.user), [f.uuid for f in queryset]
        )

        setattr(request, "_count_lookups", count_lookups)

    return count_lookups


def _feed_readCount(
    request: HttpRequest, db_obj: Feed, queryset: Collection[Feed] | None
) -> int:
    count_lookups = _feed__generate_count_lookups(request, queryset or (db_obj,))
    return count_lookups[db_obj.uuid].read_count


def _feed_unreadCount(
    request: HttpRequest, db_obj: Feed, queryset: Collection[Feed] | None
) -> int:
    count_lookups = _feed__generate_count_lookups(request, queryset or (db_obj,))
    return count_lookups[db_obj.uuid].unread_count


def _feed_isDead(
    request: HttpRequest, db_obj: Feed, queryset: Collection[Feed] | None
) -> bool:
    if db_obj.db_updated_at is None:
        return False

    now: datetime.datetime | None = getattr(request, "_now", None)
    if now is None:
        now = timezone.now()
        setattr(request, "_now", now)

    return (now - db_obj.db_updated_at) > _FEED_IS_DEAD_MAX_INTERVAL


def _feedentry_readAt(
    request: HttpRequest, db_obj: FeedEntry, queryset: Collection[FeedEntry] | None
) -> str | None:
    if queryset is None:
        try:
            read_mapping = ReadFeedEntryUserMapping.objects.get(
                user=cast(User, request.user), feed_entry=db_obj
            )
            return read_mapping.read_at.isoformat()
        except ReadFeedEntryUserMapping.DoesNotExist:
            return None
    else:
        read_at_dict: dict[uuid.UUID, datetime.datetime] | None
        if (read_at_dict := getattr(request, "_feedentry_readAt", None)) is None:
            read_at_dict = {
                mapping.feed_entry_id: mapping.read_at
                for mapping in ReadFeedEntryUserMapping.objects.filter(
                    user=cast(User, request.user),
                    feed_entry_id__in=(fe.uuid for fe in queryset),
                )
            }
            setattr(request, "_feedentry_readAt", read_at_dict)

        return (
            read_at.isoformat()
            if (read_at := read_at_dict.get(db_obj.uuid)) is not None
            else None
        )


_field_configs: dict[str, dict[str, _FieldConfig]] = {
    "usercategory": {
        "uuid": _FieldConfig(lambda request, db_obj, queryset: str(db_obj.uuid), True),
        "text": _FieldConfig(lambda request, db_obj, queryset: db_obj.text, True),
        "feedUuids": _FieldConfig(
            _usercategory_feedUuids,
            False,
        ),
    },
    "feed": {
        "uuid": _FieldConfig(lambda request, db_obj, queryset: str(db_obj.uuid), True),
        "title": _FieldConfig(lambda request, db_obj, queryset: db_obj.title, False),
        "feedUrl": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.feed_url, False
        ),
        "homeUrl": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.home_url, False
        ),
        "publishedAt": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.published_at.isoformat(), False
        ),
        "updatedAt": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.updated_at.isoformat()
            if db_obj.updated_at is not None
            else None,
            False,
        ),
        "isSubscribed": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_subscribed,
            False,
        ),
        "customTitle": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.custom_title, False
        ),
        "calculatedTitle": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.custom_title
            if db_obj.custom_title is not None
            else db_obj.title,
            False,
        ),
        "userCategoryUuids": _FieldConfig(
            _feed_userCategoryUuids,
            False,
        ),
        "readCount": _FieldConfig(_feed_readCount, False),
        "unreadCount": _FieldConfig(_feed_unreadCount, False),
        "isDead": _FieldConfig(
            _feed_isDead,
            False,
        ),
    },
    "feedentry": {
        "uuid": _FieldConfig(lambda request, db_obj, queryset: str(db_obj.uuid), True),
        "id": _FieldConfig(lambda request, db_obj, queryset: db_obj.id, False),
        "createdAt": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.created_at.isoformat()
            if db_obj.created_at is not None
            else None,
            False,
        ),
        "publishedAt": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.published_at.isoformat(), False
        ),
        "updatedAt": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.updated_at.isoformat()
            if db_obj.updated_at is not None
            else None,
            False,
        ),
        "title": _FieldConfig(lambda request, db_obj, queryset: db_obj.title, False),
        "url": _FieldConfig(lambda request, db_obj, queryset: db_obj.url, False),
        "content": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.content, False
        ),
        "authorName": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.author_name, False
        ),
        "feedUuid": _FieldConfig(
            lambda request, db_obj, queryset: str(db_obj.feed_id), False
        ),
        "isFromSubscription": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_from_subscription,
            False,
        ),
        "isRead": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_read,
            False,
        ),
        "isFavorite": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_favorite,
            False,
        ),
        "readAt": _FieldConfig(_feedentry_readAt, False),
        "isArchived": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_archived, False
        ),
        "languageIso639_3": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.language.iso639_3
            if db_obj.language is not None
            else None,
            False,
        ),
        "languageIso639_1": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.language.iso639_1
            if db_obj.language is not None
            else None,
            False,
        ),
        "languageName": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.language.name
            if db_obj.language is not None
            else None,
            False,
        ),
        "hasTopImageBeenProcessed": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.has_top_image_been_processed, False
        ),
        "topImageSrc": _FieldConfig(
            lambda request, db_obj, queryset: db_obj.top_image_src, False
        ),
    },
}


class FieldMap(TypedDict):
    field_name: str
    accessor: Callable[[HttpRequest, Any, Collection[Any] | None], Any]


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


def generate_return_object(
    field_maps: list[FieldMap],
    db_obj: Any,
    request: HttpRequest,
    queryset: Collection[Any] | None,
):
    return_obj: dict[str, Any] = {}
    for field_map in field_maps:
        field_name = field_map["field_name"]
        return_obj[field_name] = field_map["accessor"](request, db_obj, queryset)

    return return_obj
