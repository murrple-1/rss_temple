from unittest import TestCase
import datetime
from decimal import Decimal

from django.http.request import QueryDict

from api import searchqueries
from api.exceptions import QueryException


class SearchQueriesTestCase(TestCase):
    def test_context(self):
        context = searchqueries.Context()

        query_dict = QueryDict('_dtformat=%Y-%m-%d %H:%M:%S&_dformat=%Y-%m-%d&_tformat=%H:%M:%S')

        context.parse_query_dict(query_dict)

        utcnow = datetime.datetime.utcnow()

        self.assertEquals(context.format_datetime(utcnow), utcnow.strftime('%Y-%m-%d %H:%M:%S'))
        self.assertEquals(context.format_date(utcnow.date()), utcnow.date().strftime('%Y-%m-%d'))
        self.assertEquals(context.format_time(utcnow.time()), utcnow.time().strftime('%H:%M:%S'))

        d = Decimal('0.5')

        self.assertAlmostEqual(context.format_decimal(d), float(d))

    def test_serialize_content(self):
        content, content_type = searchqueries.serialize_content({
            'test1': 1,
            'test2': True
        })

        self.assertEquals(content_type, 'application/json')
        self.assertEquals(content, '{"test1":1,"test2":true}')

    def test_get_count(self):
        self.assertEquals(searchqueries.get_count(QueryDict('count=5')), 5)

        with self.assertRaises(QueryException):
            searchqueries.get_count(QueryDict('count=-1'))

        with self.assertRaises(QueryException):
            searchqueries.get_count(QueryDict('count=1001'))

        with self.assertRaises(QueryException):
            searchqueries.get_count(QueryDict('count=test'))

        self.assertEquals(searchqueries.get_count(QueryDict()), searchqueries._DEFAULT_COUNT)

        self.assertEquals(searchqueries.get_count(QueryDict('tcount=5'), param_name='tcount'), 5)

        searchqueries.get_count(QueryDict('count=1001'), max=1050)

        self.assertEquals(searchqueries.get_count(QueryDict(''), default=5), 5)

    def test_get_skip(self):
        self.assertEquals(searchqueries.get_skip(QueryDict('skip=5')), 5)

        with self.assertRaises(QueryException):
            searchqueries.get_skip(QueryDict('skip=-1'))

        with self.assertRaises(QueryException):
            searchqueries.get_skip(QueryDict('skip=test'))

        self.assertEquals(searchqueries.get_skip(QueryDict('tskip=5'), param_name='tskip'), 5)

        self.assertEquals(searchqueries.get_skip(QueryDict('')), searchqueries._DEFAULT_SKIP)

        self.assertEquals(searchqueries.get_skip(QueryDict(''), default= 5), 5)
