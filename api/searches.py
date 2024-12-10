from typing import AbstractSet, Callable, cast

from django.db import connection
from django.db.models import Q
from django.http import HttpRequest
from lingua import Language
from url_normalize import url_normalize

from api.models import AlternateFeedURL, ReadFeedEntryUserMapping, User
from query_utils.search.convertto import (
    Bool,
    CustomConvertTo,
    DateTime,
    DateTimeDeltaRange,
    DateTimeRange,
    UuidList,
)

_iso_code_639_3_names: frozenset[str] = frozenset(
    [lang.iso_code_639_3.name for lang in Language.all()] + ["UND"]
)


class LanguageIso639_3Set(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str) -> AbstractSet[str]:
        langs: set[str] = set()
        for lang in search_obj.split(","):
            lang = lang.upper()
            if lang in _iso_code_639_3_names:
                langs.add(lang)
            else:
                raise ValueError("malformed")
        return langs


_iso_code_639_1_names: frozenset[str] = frozenset(
    [lang.iso_code_639_1.name for lang in Language.all()] + ["UN"]
)


class LanguageIso639_1Set(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str) -> AbstractSet[str]:
        langs: set[str] = set()
        for lang in search_obj.split(","):
            lang = lang.upper()
            if lang in _iso_code_639_1_names:
                langs.add(lang)
            else:
                raise ValueError("malformed")
        return langs


_language_names: frozenset[str] = frozenset(
    [lang.name for lang in Language.all()] + ["UNDEFINED"]
)


class LanguageNameSet(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str) -> AbstractSet[str]:
        langs: set[str] = set()
        for lang in search_obj.split(","):
            lang = lang.upper()
            if lang in _language_names:
                langs.add(lang)
            else:
                raise ValueError("malformed")
        return langs


class URL(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str) -> str:
        try:
            return cast(str, url_normalize(search_obj))
        except Exception as e:
            raise ValueError("malformed") from e


def _feed_feedUrl(request: HttpRequest, search_obj: str) -> Q:
    url = URL.convertto(search_obj)

    return Q(feed_url=url) | Q(
        uuid__in=AlternateFeedURL.objects.filter(feed_url=url).values("feed_id")[:1]
    )


def _feedentry_feedUrl(request: HttpRequest, search_obj: str) -> Q:
    url = URL.convertto(search_obj)

    return Q(feed__feed_url=url) | Q(
        feed_id__in=AlternateFeedURL.objects.filter(feed_url=url).values("feed_id")[:1]
    )


search_fns: dict[str, dict[str, Callable[[HttpRequest, str], Q]]] = {
    "usercategory": {
        "uuid": lambda request, search_obj: Q(uuid__in=UuidList.convertto(search_obj)),
        "text": lambda request, search_obj: Q(text__icontains=search_obj),
        "text_exact": lambda request, search_obj: Q(text__iexact=search_obj),
    },
    "feed": {
        "uuid": lambda request, search_obj: Q(uuid__in=UuidList.convertto(search_obj)),
        "title": lambda request, search_obj: Q(title__icontains=search_obj),
        "title_exact": lambda request, search_obj: Q(title__iexact=search_obj),
        "feedUrl": _feed_feedUrl,
        "homeUrl": lambda request, search_obj: Q(home_url=URL.convertto(search_obj)),
        "publishedAt": lambda request, search_obj: Q(
            published_at__range=DateTimeRange.convertto(search_obj)
        ),
        "publishedAt_exact": lambda request, search_obj: Q(
            published_at=DateTime.convertto(search_obj)
        ),
        "publishedAt_delta": lambda request, search_obj: Q(
            published_at__range=DateTimeDeltaRange.convertto(search_obj)
        ),
        "updatedAt": lambda request, search_obj: Q(
            updated_at__range=DateTimeRange.convertto(search_obj)
        ),
        "updatedAt_exact": lambda request, search_obj: Q(
            updated_at=DateTime.convertto(search_obj)
        ),
        "updatedAt_delta": lambda request, search_obj: Q(
            updated_at__range=DateTimeDeltaRange.convertto(search_obj)
        ),
        "isSubscribed": lambda request, search_obj: Q(
            is_subscribed=Bool.convertto(search_obj)
        ),
        "customTitle": lambda request, search_obj: Q(
            custom_title__icontains=search_obj
        ),
        "customTitle_exact": lambda request, search_obj: Q(
            custom_title__iexact=search_obj
        ),
        "customTitle_null": lambda request, search_obj: Q(
            custom_title__isnull=Bool.convertto(search_obj)
        ),
        "calculatedTitle": lambda request, search_obj: Q(title__icontains=search_obj)
        | Q(custom_title__icontains=search_obj),
        "calculatedTitle_exact": lambda request, search_obj: Q(title__iexact=search_obj)
        | Q(custom_title__iexact=search_obj),
    },
    "feedentry": {
        "uuid": lambda request, search_obj: Q(uuid__in=UuidList.convertto(search_obj)),
        "feedUuid": lambda request, search_obj: Q(
            feed_id__in=UuidList.convertto(search_obj)
        ),
        "feedUrl": _feedentry_feedUrl,
        "createdAt": lambda request, search_obj: Q(
            created_at__range=DateTimeRange.convertto(search_obj)
        ),
        "createdAt_exact": lambda request, search_obj: Q(
            created_at=DateTime.convertto(search_obj)
        ),
        "createdAt_delta": lambda request, search_obj: Q(
            created_at__range=DateTimeDeltaRange.convertto(search_obj)
        ),
        "publishedAt": lambda request, search_obj: Q(
            published_at__range=DateTimeRange.convertto(search_obj)
        ),
        "publishedAt_exact": lambda request, search_obj: Q(
            published_at=DateTime.convertto(search_obj)
        ),
        "publishedAt_delta": lambda request, search_obj: Q(
            published_at__range=DateTimeDeltaRange.convertto(search_obj)
        ),
        "updatedAt": lambda request, search_obj: Q(
            updated_at__range=DateTimeRange.convertto(search_obj)
        ),
        "updatedAt_exact": lambda request, search_obj: Q(
            updated_at=DateTime.convertto(search_obj)
        ),
        "updatedAt_delta": lambda request, search_obj: Q(
            updated_at__range=DateTimeDeltaRange.convertto(search_obj)
        ),
        "url": lambda request, search_obj: Q(url__iexact=search_obj),
        "authorName": lambda request, search_obj: Q(author_name__icontains=search_obj),
        "authorName_exact": lambda request, search_obj: Q(
            author_name__iexact=search_obj
        ),
        "isFromSubscription": lambda request, search_obj: Q(
            is_from_subscription=Bool.convertto(search_obj)
        ),
        "isRead": lambda request, search_obj: Q(is_read=Bool.convertto(search_obj)),
        "isFavorite": lambda request, search_obj: Q(
            is_favorite=Bool.convertto(search_obj)
        ),
        "readAt": lambda request, search_obj: Q(
            uuid__in=ReadFeedEntryUserMapping.objects.filter(
                user=cast(User, request.user),
                read_at__range=DateTimeRange.convertto(search_obj),
            )
        ),
        "readAt_exact": lambda request, search_obj: Q(
            uuid__in=ReadFeedEntryUserMapping.objects.filter(
                user=cast(User, request.user), read_at=DateTime.convertto(search_obj)
            )
        ),
        "readAt_delta": lambda request, search_obj: Q(
            uuid__in=ReadFeedEntryUserMapping.objects.filter(
                user=cast(User, request.user),
                read_at__range=DateTimeDeltaRange.convertto(search_obj),
            )
        ),
        "isArchived": lambda request, search_obj: Q(
            is_archived=Bool.convertto(search_obj)
        ),
        "languageIso639_3": lambda request, search_obj: Q(
            language__iso639_3__in=LanguageIso639_3Set.convertto(search_obj)
        ),
        "languageIso639_1": lambda request, search_obj: Q(
            language__iso639_1__in=LanguageIso639_1Set.convertto(search_obj)
        ),
        "languageName": lambda request, search_obj: Q(
            language__name__in=LanguageNameSet.convertto(search_obj)
        ),
        "hasTopImageBeenProcessed": lambda request, search_obj: Q(
            has_top_image_been_processed=Bool.convertto(search_obj)
        ),
    },
}

if connection.vendor == "postgresql":  # pragma: no cover
    search_fns["feed"]["title"] = lambda request, search_obj: Q(
        title_search_vector=search_obj
    )
    search_fns["feedentry"]["title"] = lambda request, search_obj: Q(
        title_search_vector=search_obj
    )
    search_fns["feedentry"]["content"] = lambda request, search_obj: Q(
        content_search_vector=search_obj
    )
else:
    search_fns["feed"]["title"] = lambda request, search_obj: Q(
        title__icontains=search_obj
    )
    search_fns["feedentry"]["title"] = lambda request, search_obj: Q(
        title__icontains=search_obj
    )
    search_fns["feedentry"]["content"] = lambda request, search_obj: Q(
        content__icontains=search_obj
    )
