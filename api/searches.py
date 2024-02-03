import logging
from typing import Callable, cast

from django.db import connection
from django.db.models import Q
from django.http import HttpRequest
from lingua import Language
from pyparsing import ParseException, ParseResults

from api.models import Feed, ReadFeedEntryUserMapping, SubscribedFeedUserMapping, User
from api.search.convertto import (
    Bool,
    CustomConvertTo,
    DateTime,
    DateTimeDeltaRange,
    DateTimeRange,
    UuidList,
)
from api.search.parser import parser

_logger = logging.getLogger("rss_temple")


_iso_code_639_3_names: frozenset[str] = frozenset(
    [l.iso_code_639_3.name for l in Language.all()] + ["UND"]
)


class LanguageIso639_3Set(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        langs: set[str] = set()
        for l in search_obj.split(","):
            l = l.upper()
            if l in _iso_code_639_3_names:
                langs.add(l)
            else:
                raise ValueError("malformed")
        return langs


_iso_code_639_1_names: frozenset[str] = frozenset(
    [l.iso_code_639_1.name for l in Language.all()] + ["UN"]
)


class LanguageIso639_1Set(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        langs: set[str] = set()
        for l in search_obj.split(","):
            l = l.upper()
            if l in _iso_code_639_1_names:
                langs.add(l)
            else:
                raise ValueError("malformed")
        return langs


_language_names: frozenset[str] = frozenset(
    [l.name for l in Language.all()] + ["UNDEFINED"]
)


class LanguageNameSet(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        langs: set[str] = set()
        for l in search_obj.split(","):
            l = l.upper()
            if l in _language_names:
                langs.add(l)
            else:
                raise ValueError("malformed")
        return langs


def _feedentry_subscribed(request: HttpRequest, search_obj: str):
    q = Q(
        feed__in=Feed.objects.filter(
            uuid__in=SubscribedFeedUserMapping.objects.filter(
                user=cast(User, request.user)
            ).values("feed_id")
        )
    )

    if not Bool.convertto(search_obj):
        q = ~q

    return q


def _feedentry_is_read(request: HttpRequest, search_obj: str):
    q = Q(is_archived=True) | Q(
        uuid__in=ReadFeedEntryUserMapping.objects.filter(
            user=cast(User, request.user)
        ).values("feed_entry_id")
    )

    if not Bool.convertto(search_obj):
        q = ~q

    return q


def _feedentry_is_favorite(request: HttpRequest, search_obj: str):
    q = Q(uuid__in=cast(User, request.user).favorite_feed_entries.values("uuid"))

    if not Bool.convertto(search_obj):
        q = ~q

    return q


_search_fns: dict[str, dict[str, Callable[[HttpRequest, str], Q]]] = {
    "usercategory": {
        "uuid": lambda request, search_obj: Q(uuid__in=UuidList.convertto(search_obj)),
        "text": lambda request, search_obj: Q(text__icontains=search_obj),
        "text_exact": lambda request, search_obj: Q(text__iexact=search_obj),
    },
    "feed": {
        "uuid": lambda request, search_obj: Q(uuid__in=UuidList.convertto(search_obj)),
        "title": lambda request, search_obj: Q(title__icontains=search_obj),
        "title_exact": lambda request, search_obj: Q(title__iexact=search_obj),
        "feedUrl": lambda request, search_obj: Q(feed_url__iexact=search_obj),
        "homeUrl": lambda request, search_obj: Q(home_url__iexact=search_obj),
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
        "subscribed": lambda request, search_obj: Q(
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
        "feedUrl": lambda request, search_obj: Q(feed__feed_url=search_obj),
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
        "subscribed": _feedentry_subscribed,
        "isRead": _feedentry_is_read,
        "isFavorite": _feedentry_is_favorite,
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
    _search_fns["feed"]["title"] = lambda request, search_obj: Q(
        title_search_vector=search_obj
    )
    _search_fns["feedentry"]["title"] = lambda request, search_obj: Q(
        title_search_vector=search_obj
    )
    _search_fns["feedentry"]["content"] = lambda request, search_obj: Q(
        content_search_vector=search_obj
    )
else:
    _search_fns["feed"]["title"] = lambda request, search_obj: Q(
        title__icontains=search_obj
    )
    _search_fns["feedentry"]["title"] = lambda request, search_obj: Q(
        title__icontains=search_obj
    )
    _search_fns["feedentry"]["content"] = lambda request, search_obj: Q(
        content__icontains=search_obj
    )


def to_filter_args(object_name: str, request: HttpRequest, search: str) -> list[Q]:
    parse_results: ParseResults
    try:
        parse_results = parser().parseString(search, True)
    except ParseException as e:
        _logger.warning("Parsing of '%s' failed: %s", search, e)
        raise ValueError("search malformed")

    object_search_fns = _search_fns[object_name]

    return [_handle_parse_result(request, parse_results, object_search_fns)]


def _handle_parse_result(
    request: HttpRequest, parse_results: ParseResults, object_search_fns
) -> Q:
    if "WhereClause" in parse_results and "WhereExpressionExtension" in parse_results:
        where_clause = parse_results["WhereClause"]
        where_expression_extension = parse_results["WhereExpressionExtension"]
        if "AndOperator" in where_expression_extension:
            return _handle_parse_result(
                request, cast(ParseResults, where_clause), object_search_fns
            ) & _handle_parse_result(
                request,
                cast(ParseResults, where_expression_extension),
                object_search_fns,
            )
        elif "OrOperator" in where_expression_extension:
            return _handle_parse_result(
                request, cast(ParseResults, where_clause), object_search_fns
            ) | _handle_parse_result(
                request,
                cast(ParseResults, where_expression_extension),
                object_search_fns,
            )
        else:
            return _handle_parse_result(
                request, cast(ParseResults, where_clause), object_search_fns
            )
    elif "NamedExpression" in parse_results:
        named_expression = cast(ParseResults, parse_results["NamedExpression"])
        field_name = cast(str, named_expression["IdentifierTerm"])
        # if search_obj is "" (empty string), 'StringTerm' will not exist, so default it
        search_obj = cast(
            str,
            named_expression["StringTerm"] if "StringTerm" in named_expression else "",
        )

        return _q(request, field_name, search_obj, object_search_fns)
    elif "ExcludeNamedExpression" in parse_results:
        exclude_named_expression = cast(
            ParseResults, parse_results["ExcludeNamedExpression"]
        )
        field_name = cast(str, exclude_named_expression["IdentifierTerm"])
        # if search_obj is "" (empty string), 'StringTerm' will not exist, so default it
        search_obj = cast(
            str,
            exclude_named_expression["StringTerm"]
            if "StringTerm" in exclude_named_expression
            else "",
        )

        return ~_q(request, field_name, search_obj, object_search_fns)
    elif "ParenthesizedExpression" in parse_results:
        return Q(
            _handle_parse_result(
                request,
                cast(ParseResults, parse_results["ParenthesizedExpression"]),
                object_search_fns,
            )
        )
    else:  # pragma: no cover
        raise ValueError("unknown parse_result")


def _q(
    request: HttpRequest,
    field_name: str,
    search_obj: str,
    object_search_fns: dict[str, Callable[[HttpRequest, str], Q]],
) -> Q:
    for _field_name, object_search_fn in object_search_fns.items():
        if field_name.lower() == _field_name.lower():
            try:
                return object_search_fn(request, search_obj)
            except ValueError:
                raise ValueError(f"'{field_name}' search malformed")
    else:
        raise AttributeError(field_name)
