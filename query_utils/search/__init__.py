import logging
from typing import Callable, cast

from django.db.models import Q
from django.http import HttpRequest
from pyparsing import ParseException, ParseResults

from query_utils.search.parser import parser

_logger = logging.getLogger(__name__)


def to_filter_args(
    object_name: str,
    request: HttpRequest,
    search: str,
    search_fns: dict[str, dict[str, Callable[[HttpRequest, str], Q]]],
) -> list[Q]:
    parse_results: ParseResults
    try:
        parse_results = parser().parseString(search, True)
    except ParseException as e:
        _logger.warning("Parsing of '%s' failed: %s", search, e)
        raise ValueError("search malformed")

    object_search_fns = search_fns[object_name]

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
            (
                exclude_named_expression["StringTerm"]
                if "StringTerm" in exclude_named_expression
                else ""
            ),
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
