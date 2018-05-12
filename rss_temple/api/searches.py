import logging

from django.db.models import Q

from pyparsing import ParseException

from api.exceptions import QueryException
from api.search.parser import parser
import api.search.convertto as convertto

_logger = logging.getLogger('rss_temple')


__search_fns = {
    'user': {
        'uuid': lambda search_obj: Q(uuid__in=convertto.UuidList.convertto(search_obj)),
        'email': lambda search_obj: Q(email__icontains=search_obj),
        'email_exact': lambda search_obj: Q(email__iexact=search_obj),
    },
    'feed': {
        'uuid': lambda search_obj: Q(uuid__in=convertto.UuidList.convertto(search_obj)),
    },
}


def to_filter_args(object_name, search):
    parse_results = None
    try:
        parse_results = parser().parseString(search, True)
    except ParseException as e:
        _logger.warning('Parsing of \'%s\' failed: %s', search, e)
        raise QueryException('\'search\' malformed', 400)

    object_search_fns = __search_fns[object_name]

    return [_handle_parse_result(parse_results.asDict(), object_search_fns)]


def _handle_parse_result(results_dict, object_search_fns):
    if 'WhereExpression' in results_dict:
        where_expression = results_dict['WhereExpression'][0]
        if 'WhereExpressionExtension' in where_expression:
            where_expression_extension = where_expression['WhereExpressionExtension']
            if 'AndOperator' in where_expression_extension:
                return (
                    _handle_parse_result(
                        where_expression,
                        object_search_fns) & _handle_parse_result(
                        where_expression_extension,
                        object_search_fns))
            elif 'OrOperator' in where_expression_extension:
                return (
                    _handle_parse_result(
                        where_expression,
                        object_search_fns) | _handle_parse_result(
                        where_expression_extension,
                        object_search_fns))
        else:
            return _handle_parse_result(where_expression, object_search_fns)
    elif 'WhereClause' in results_dict:
        return _handle_parse_result(
            results_dict['WhereClause'],
            object_search_fns)
    elif 'NamedExpression' in results_dict:
        named_expression = results_dict['NamedExpression']
        field_name = named_expression['IdentifierTerm']
        search_obj = named_expression['StringTerm'] if 'StringTerm' in named_expression else ''

        return _q(field_name, search_obj, object_search_fns)
    elif 'ExcludeNamedExpression' in results_dict:
        exclude_named_expression = results_dict['ExcludeNamedExpression']
        field_name = exclude_named_expression['IdentifierTerm']
        search_obj = exclude_named_expression['StringTerm'] if 'StringTerm' in exclude_named_expression else ''

        return ~_q(field_name, search_obj, object_search_fns)
    elif 'ParenthesizedExpression' in results_dict:
        return Q(
            _handle_parse_result(
                results_dict['ParenthesizedExpression'],
                object_search_fns))


def _q(field_name, search_obj, object_search_fns):
    for _field_name, object_search_fn in object_search_fns.items():
        if field_name.lower() == _field_name.lower():
            try:
                return object_search_fn(search_obj)
            except ValueError:
                raise QueryException(
                    '\'{0}\' search malformed'.format(field_name), 400)
    raise QueryException(
        '\'{0}\' field not recognized'.format(field_name), 400)
