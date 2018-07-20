from pyparsing import Word, Group, alphas, alphanums, Forward, QuotedString, ZeroOrMore, CaselessKeyword, Suppress

_parser = None


def parser():
    global _parser

    if not _parser:
        string_term = QuotedString('"').setResultsName('StringTerm')
        identifier_term = Word(alphas, alphanums + '_'
                               ).setResultsName('IdentifierTerm')

        and_operator = CaselessKeyword('and').setResultsName('AndOperator')
        or_operator = CaselessKeyword('or').setResultsName('OrOperator')

        where_expression = Forward()

        named_expression = Group(
            identifier_term + Suppress(':') + string_term
        ).setResultsName('NamedExpression')
        exclude_named_expression = Group(
            identifier_term + Suppress(':!') + string_term
        ).setResultsName('ExcludeNamedExpression')
        parenthesized_expression = Group(
            Suppress('(') + where_expression + Suppress(')')
        ).setResultsName('ParenthesizedExpression')

        where_clause = Group(
            named_expression |
            exclude_named_expression |
            parenthesized_expression
        ).setResultsName('WhereClause')

        where_expression_extension = Group(
            ZeroOrMore(
                (and_operator | or_operator) + where_expression)
        ).setResultsName('WhereExpressionExtension')

        where_expression << (where_clause + where_expression_extension)

        _parser = where_expression

    return _parser
