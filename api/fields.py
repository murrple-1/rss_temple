import datetime
import logging
import uuid
from collections import defaultdict
from typing import Any, Iterable, cast

from django.conf import settings
from django.core.signals import setting_changed
from django.db.models import QuerySet
from django.dispatch import receiver
from django.http import HttpRequest
from django.utils import timezone

from api.models import Feed, FeedEntry, ReadFeedEntryUserMapping, User, UserCategory
from query_utils.fields import FieldConfig

_logger = logging.getLogger("rss_temple.fields")

_FEED_IS_DEAD_MAX_INTERVAL: datetime.timedelta


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _FEED_IS_DEAD_MAX_INTERVAL

    _FEED_IS_DEAD_MAX_INTERVAL = settings.FEED_IS_DEAD_MAX_INTERVAL


_load_global_settings()


def _usercategory_feedUuids(
    request: HttpRequest,
    db_obj: UserCategory,
    queryset: Iterable[UserCategory] | None,
) -> list[str]:
    if queryset is None:
        return [str(uuid_) for uuid_ in db_obj.feed_uuids]
    else:
        feed_uuids_dict: dict[uuid.UUID, list[uuid.UUID]] | None
        if (
            feed_uuids_dict := getattr(request, "_usercategory_feedUuids", None)
        ) is None:
            if isinstance(queryset, QuerySet):
                feed_uuids_dict = defaultdict(list)
                for t in UserCategory.feeds.through.objects.filter(
                    usercategory_id__in=queryset.values("uuid")
                ):
                    feed_uuids_dict[t.usercategory_id].append(t.feed_id)
            else:
                feed_uuids_dict = {uc.uuid: [] for uc in queryset}
                for t in UserCategory.feeds.through.objects.filter(
                    usercategory_id__in=feed_uuids_dict.keys()
                ):
                    feed_uuids_dict[t.usercategory_id].append(t.feed_id)

            setattr(request, "_usercategory_feedUuids", feed_uuids_dict)

        return [str(uuid_) for uuid_ in feed_uuids_dict[db_obj.uuid]]


def _feed_userCategoryUuids(
    request: HttpRequest, db_obj: Feed, queryset: Iterable[Feed] | None
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
            if isinstance(queryset, QuerySet):
                user_category_uuids_dict = defaultdict(list)
                for t in UserCategory.feeds.through.objects.filter(
                    usercategory__user=cast(User, request.user),
                    feed_id__in=queryset.values("uuid"),
                ):
                    user_category_uuids_dict[t.feed_id].append(t.usercategory_id)
            else:
                user_category_uuids_dict = {f.uuid: [] for f in queryset}
                for t in UserCategory.feeds.through.objects.filter(
                    usercategory__user=cast(User, request.user),
                    feed_id__in=user_category_uuids_dict.keys(),
                ):
                    user_category_uuids_dict[t.feed_id].append(t.usercategory_id)

            setattr(request, "_feed_userCategoryUuids", user_category_uuids_dict)

        return [str(uuid_) for uuid_ in user_category_uuids_dict[db_obj.uuid]]


def _feed__generate_counts_lookup(
    request: HttpRequest, queryset: Iterable[Feed]
) -> dict[uuid.UUID, Feed._CountsDescriptor]:
    counts_lookup: dict[uuid.UUID, Feed._CountsDescriptor] | None = getattr(
        request, "_counts_lookup", None
    )
    if counts_lookup is None:
        _logger.warning("slow path: _feed__generate_counts_lookup")
        counts_lookup = Feed.generate_counts_lookup(
            cast(User, request.user), [f.uuid for f in queryset]
        )

        setattr(request, "_counts_lookup", counts_lookup)

    return counts_lookup


def _feed_readCount(
    request: HttpRequest, db_obj: Feed, queryset: Iterable[Feed] | None
) -> int:
    counts_lookup = _feed__generate_counts_lookup(request, queryset or (db_obj,))
    return counts_lookup[db_obj.uuid].read_count


def _feed_unreadCount(
    request: HttpRequest, db_obj: Feed, queryset: Iterable[Feed] | None
) -> int:
    counts_lookup = _feed__generate_counts_lookup(request, queryset or (db_obj,))
    return counts_lookup[db_obj.uuid].unread_count


def _feed__generate_archived_counts_lookup(
    request: HttpRequest, queryset: Iterable[Feed]
) -> dict[uuid.UUID, int]:
    archived_counts_lookup: dict[uuid.UUID, int] | None = getattr(
        request, "_archived_counts_lookup", None
    )
    if archived_counts_lookup is None:
        _logger.warning("slow path: _feed__generate_archived_counts_lookup")
        archived_counts_lookup = Feed.generate_archived_counts_lookup(
            [f.uuid for f in queryset]
        )

        setattr(request, "_archived_counts_lookup", archived_counts_lookup)

    return archived_counts_lookup


def _feed_archivedCount(
    request: HttpRequest, db_obj: Feed, queryset: Iterable[Feed] | None
) -> int:
    archived_counts_lookup = _feed__generate_archived_counts_lookup(
        request, queryset or (db_obj,)
    )
    return archived_counts_lookup[db_obj.uuid]


def _feed_isDead(
    request: HttpRequest, db_obj: Feed, queryset: Iterable[Feed] | None
) -> bool:
    if db_obj.db_updated_at is None:
        return False

    now: datetime.datetime | None = getattr(request, "_now", None)
    if now is None:
        now = timezone.now()
        setattr(request, "_now", now)

    return (now - db_obj.db_updated_at) > _FEED_IS_DEAD_MAX_INTERVAL


def _feedentry_readAt(
    request: HttpRequest, db_obj: FeedEntry, queryset: Iterable[FeedEntry] | None
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


field_configs: dict[str, dict[str, FieldConfig]] = {
    "usercategory": {
        "uuid": FieldConfig(
            lambda request, db_obj, queryset: str(db_obj.uuid),
            True,
            {"uuid"},
        ),
        "text": FieldConfig(
            lambda request, db_obj, queryset: db_obj.text,
            True,
            {"text"},
        ),
        "feedUuids": FieldConfig(
            _usercategory_feedUuids,
            False,
            {"uuid"},
        ),
    },
    "feed": {
        "uuid": FieldConfig(
            lambda request, db_obj, queryset: str(db_obj.uuid),
            True,
            {"uuid"},
        ),
        "title": FieldConfig(
            lambda request, db_obj, queryset: db_obj.title,
            False,
            {"title"},
        ),
        "feedUrl": FieldConfig(
            lambda request, db_obj, queryset: db_obj.feed_url,
            False,
            {"feed_url"},
        ),
        "homeUrl": FieldConfig(
            lambda request, db_obj, queryset: db_obj.home_url,
            False,
            {"home_url"},
        ),
        "publishedAt": FieldConfig(
            lambda request, db_obj, queryset: db_obj.published_at.isoformat(),
            False,
            {"published_at"},
        ),
        "updatedAt": FieldConfig(
            lambda request, db_obj, queryset: (
                db_obj.updated_at.isoformat() if db_obj.updated_at is not None else None
            ),
            False,
            {"updated_at"},
        ),
        "isSubscribed": FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_subscribed,
            False,
            frozenset(),
        ),
        "customTitle": FieldConfig(
            lambda request, db_obj, queryset: db_obj.custom_title,
            False,
            frozenset(),
        ),
        "calculatedTitle": FieldConfig(
            lambda request, db_obj, queryset: (
                db_obj.custom_title if db_obj.custom_title is not None else db_obj.title
            ),
            False,
            {"title"},
        ),
        "userCategoryUuids": FieldConfig(
            _feed_userCategoryUuids,
            False,
            {"uuid"},
        ),
        "readCount": FieldConfig(_feed_readCount, False, {"uuid"}),
        "unreadCount": FieldConfig(_feed_unreadCount, False, {"uuid"}),
        "archivedCount": FieldConfig(_feed_archivedCount, False, {"uuid"}),
        "isDead": FieldConfig(
            _feed_isDead,
            False,
            {"db_updated_at"},
        ),
    },
    "feedentry": {
        "uuid": FieldConfig(
            lambda request, db_obj, queryset: str(db_obj.uuid),
            True,
            {"uuid"},
        ),
        "id": FieldConfig(
            lambda request, db_obj, queryset: db_obj.id,
            False,
            {"id"},
        ),
        "createdAt": FieldConfig(
            lambda request, db_obj, queryset: (
                db_obj.created_at.isoformat() if db_obj.created_at is not None else None
            ),
            False,
            {"created_at"},
        ),
        "publishedAt": FieldConfig(
            lambda request, db_obj, queryset: db_obj.published_at.isoformat(),
            False,
            {"published_at"},
        ),
        "updatedAt": FieldConfig(
            lambda request, db_obj, queryset: (
                db_obj.updated_at.isoformat() if db_obj.updated_at is not None else None
            ),
            False,
            {"updated_at"},
        ),
        "title": FieldConfig(
            lambda request, db_obj, queryset: db_obj.title,
            False,
            {"title"},
        ),
        "url": FieldConfig(
            lambda request, db_obj, queryset: db_obj.url,
            False,
            {"url"},
        ),
        "content": FieldConfig(
            lambda request, db_obj, queryset: db_obj.content,
            False,
            {"content"},
        ),
        "authorName": FieldConfig(
            lambda request, db_obj, queryset: db_obj.author_name,
            False,
            {"author_name"},
        ),
        "feedUuid": FieldConfig(
            lambda request, db_obj, queryset: str(db_obj.feed_id),
            False,
            {"feed_id"},
        ),
        "isFromSubscription": FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_from_subscription,
            False,
            frozenset(),
        ),
        "isRead": FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_read,
            False,
            frozenset(),
        ),
        "isFavorite": FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_favorite,
            False,
            frozenset(),
        ),
        "readAt": FieldConfig(
            _feedentry_readAt,
            False,
            frozenset(),
        ),
        "isArchived": FieldConfig(
            lambda request, db_obj, queryset: db_obj.is_archived,
            False,
            {"is_archived"},
        ),
        "languageIso639_3": FieldConfig(
            lambda request, db_obj, queryset: (
                db_obj.language.iso639_3 if db_obj.language is not None else None
            ),
            False,
            {"language"},
        ),
        "languageIso639_1": FieldConfig(
            lambda request, db_obj, queryset: (
                db_obj.language.iso639_1 if db_obj.language is not None else None
            ),
            False,
            {"language"},
        ),
        "languageName": FieldConfig(
            lambda request, db_obj, queryset: (
                db_obj.language.name if db_obj.language is not None else None
            ),
            False,
            {"language"},
        ),
        "hasTopImageBeenProcessed": FieldConfig(
            lambda request, db_obj, queryset: db_obj.has_top_image_been_processed,
            False,
            {"has_top_image_been_processed"},
        ),
        "topImageSrc": FieldConfig(
            lambda request, db_obj, queryset: db_obj.top_image_src,
            False,
            {"top_image_src"},
        ),
    },
}
