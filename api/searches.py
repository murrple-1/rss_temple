import logging

from django.db import connection
from django.db.models import Q
from pyparsing import ParseException

from api import models
from api.exceptions import QueryException
from api.search.convertto import (
    Bool,
    DateTime,
    DateTimeDeltaRange,
    DateTimeRange,
    UuidList,
)
from api.search.parser import parser

_logger = logging.getLogger("rss_temple")


def _feedentry_subscribed(request, search_obj):
    q = Q(
        feed__in=models.Feed.objects.filter(
            uuid__in=models.SubscribedFeedUserMapping.objects.filter(
                user=request.user
            ).values("feed_id")
        )
    )

    if not Bool.convertto(search_obj):
        q = ~q

    return q


def _feedentry_is_read(request, search_obj):
    q = Q(
        uuid__in=models.ReadFeedEntryUserMapping.objects.filter(
            user=request.user
        ).values("feed_entry_id")
    )

    if not Bool.convertto(search_obj):
        q = ~q

    return q


def _feedentry_is_favorite(request, search_obj):
    q = Q(
        uuid__in=models.FavoriteFeedEntryUserMapping.objects.filter(
            user=request.user
        ).values("feed_entry_id")
    )

    if not Bool.convertto(search_obj):
        q = ~q

    return q


_search_fns = {
    "user": {
        "uuid": lambda request, search_obj: Q(uuid__in=UuidList.convertto(search_obj)),
        "email": lambda request, search_obj: Q(email__icontains=search_obj),
        "email_exact": lambda request, search_obj: Q(email__iexact=search_obj),
    },
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
            uuid__in=models.ReadFeedEntryUserMapping.objects.filter(
                user=request.user,
                read_at__range=DateTimeRange.convertto(search_obj),
            )
        ),
        "readAt_exact": lambda request, search_obj: Q(
            uuid__in=models.ReadFeedEntryUserMapping.objects.filter(
                user=request.user, read_at=DateTime.convertto(search_obj)
            )
        ),
        "readAt_delta": lambda request, search_obj: Q(
            uuid__in=models.ReadFeedEntryUserMapping.objects.filter(
                user=request.user,
                read_at__range=DateTimeDeltaRange.convertto(search_obj),
            )
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


def to_filter_args(object_name, request, search):
    parse_results = None
    try:
        parse_results = parser().parseString(search, True)
    except ParseException as e:
        _logger.warning("Parsing of '%s' failed: %s", search, e)
        raise QueryException("'search' malformed", 400)

    object_search_fns = _search_fns[object_name]

    return [_handle_parse_result(request, parse_results, object_search_fns)]


def _handle_parse_result(request, parse_results, object_search_fns):
    if "WhereClause" in parse_results and "WhereExpressionExtension" in parse_results:
        where_clause = parse_results["WhereClause"]
        where_expression_extension = parse_results["WhereExpressionExtension"]
        if "AndOperator" in where_expression_extension:
            return _handle_parse_result(
                request, where_clause, object_search_fns
            ) & _handle_parse_result(
                request, where_expression_extension, object_search_fns
            )
        elif "OrOperator" in where_expression_extension:
            return _handle_parse_result(
                request, where_clause, object_search_fns
            ) | _handle_parse_result(
                request, where_expression_extension, object_search_fns
            )
        else:
            return _handle_parse_result(request, where_clause, object_search_fns)
    elif "NamedExpression" in parse_results:
        named_expression = parse_results["NamedExpression"]
        field_name = named_expression["IdentifierTerm"]
        # if search_obj is "" (empty string), 'StringTerm' will not exist, so default it
        search_obj = (
            named_expression["StringTerm"] if "StringTerm" in named_expression else ""
        )

        return _q(request, field_name, search_obj, object_search_fns)
    elif "ExcludeNamedExpression" in parse_results:
        exclude_named_expression = parse_results["ExcludeNamedExpression"]
        field_name = exclude_named_expression["IdentifierTerm"]
        # if search_obj is "" (empty string), 'StringTerm' will not exist, so default it
        search_obj = (
            exclude_named_expression["StringTerm"]
            if "StringTerm" in exclude_named_expression
            else ""
        )

        return ~_q(request, field_name, search_obj, object_search_fns)
    elif "ParenthesizedExpression" in parse_results:
        return Q(
            _handle_parse_result(
                request, parse_results["ParenthesizedExpression"], object_search_fns
            )
        )


def _q(request, field_name, search_obj, object_search_fns):
    for _field_name, object_search_fn in object_search_fns.items():
        if field_name.lower() == _field_name.lower():
            try:
                return object_search_fn(request, search_obj)
            except ValueError:
                raise QueryException(f"'{field_name}' search malformed", 400)
    else:
        raise QueryException(f"'{field_name}' field not recognized", 400)
