from unittest import TestCase
import datetime
from decimal import Decimal

from django.http.request import QueryDict

from api import searchqueries


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
