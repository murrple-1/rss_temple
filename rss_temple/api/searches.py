import logging

from django.db.models import Q

from pyparsing import ParseException

from api.exceptions import QueryException
from api.search.parser import parser
from api.search import convertto

_logger = logging.getLogger('rss_temple')


__search_fns = {
    'user': {
        'uuid': lambda context, search_obj: Q(uuid__in=convertto.UuidList.convertto(search_obj)),
        'email': lambda context, search_obj: Q(email__icontains=search_obj),
        'email_exact': lambda context, search_obj: Q(email__iexact=search_obj),
    },
    'feed': {
        'uuid': lambda context, search_obj: Q(uuid__in=convertto.UuidList.convertto(search_obj)),
    },
    # TODO
    'feedentry': {
        'uuid': lambda context, search_obj: Q(uuid__in=convertto.UuidList.convertto(search_obj)),
        'feedUuid': lambda context, search_obj: Q(feed_id__in=convertto.UuidList.convertto(search_obj)),
        'feedUrl': lambda context, search_obj: Q(feed__feed_url=search_obj),
    },
}


def to_filter_args(object_name, context, search):
    parse_results = None
    try:
        parse_results = parser().parseString(search, True)
    except ParseException as e:
        _logger.warning('Parsing of \'%s\' failed: %s', search, e)
        raise QueryException('\'search\' malformed', 400)

    object_search_fns = __search_fns[object_name]

    return [_handle_parse_result(context, parse_results, object_search_fns)]


def _handle_parse_result(context, parse_results, object_search_fns):
    if 'WhereClause' in parse_results and 'WhereExpressionExtension' in parse_results:
        where_clause = parse_results['WhereClause']
        where_expression_extension = parse_results['WhereExpressionExtension']
        if 'AndOperator' in where_expression_extension:
            return (
                _handle_parse_result(
                    context,
                    where_clause,
                    object_search_fns) & _handle_parse_result(
                    context,
                    where_expression_extension,
                    object_search_fns))
        elif 'OrOperator' in where_expression_extension:
            return (
                _handle_parse_result(
                    context,
                    where_clause,
                    object_search_fns) | _handle_parse_result(
                    context,
                    where_expression_extension,
                    object_search_fns))
        else:
            return _handle_parse_result(
                context,
                where_clause,
                object_search_fns)
    elif 'NamedExpression' in parse_results:
        named_expression = parse_results['NamedExpression']
        field_name = named_expression['IdentifierTerm']
        # if search_obj is "" (empty string), 'StringTerm' will not exist, so default it
        search_obj = named_expression['StringTerm'] if 'StringTerm' in named_expression else ''

        return _q(context, field_name, search_obj, object_search_fns)
    elif 'ExcludeNamedExpression' in parse_results:
        exclude_named_expression = parse_results['ExcludeNamedExpression']
        field_name = exclude_named_expression['IdentifierTerm']
        # if search_obj is "" (empty string), 'StringTerm' will not exist, so default it
        search_obj = exclude_named_expression['StringTerm'] if 'StringTerm' in exclude_named_expression else ''

        return ~_q(context, field_name, search_obj, object_search_fns)
    elif 'ParenthesizedExpression' in parse_results:
        return Q(
            _handle_parse_result(
                context,
                parse_results['ParenthesizedExpression'],
                object_search_fns))


def _q(context, field_name, search_obj, object_search_fns):
    for _field_name, object_search_fn in object_search_fns.items():
        if field_name.lower() == _field_name.lower():
            try:
                return object_search_fn(context, search_obj)
            except ValueError:
                raise QueryException(
                    '\'{0}\' search malformed'.format(field_name), 400)
    else:
        raise QueryException(
            '\'{0}\' field not recognized'.format(field_name), 400)
