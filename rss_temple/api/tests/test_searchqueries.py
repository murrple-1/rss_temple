import datetime
from decimal import Decimal

from django.test import TestCase
from django.http.request import QueryDict

from api import searchqueries
from api.exceptions import QueryException
from api.context import Context


class SearchQueriesTestCase(TestCase):
    def test_context(self):
        context = Context()

        query_dict = QueryDict(
            '_dtformat=%Y-%m-%d %H:%M:%S&_dformat=%Y-%m-%d&_tformat=%H:%M:%S')

        context.parse_query_dict(query_dict)

        utcnow = datetime.datetime.utcnow()

        self.assertEquals(context.format_datetime(utcnow),
                          utcnow.strftime('%Y-%m-%d %H:%M:%S'))
        self.assertEquals(context.format_date(utcnow.date()),
                          utcnow.date().strftime('%Y-%m-%d'))
        self.assertEquals(context.format_time(utcnow.time()),
                          utcnow.time().strftime('%H:%M:%S'))

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

        self.assertEquals(searchqueries.get_count(
            QueryDict()), searchqueries._DEFAULT_COUNT)

        self.assertEquals(searchqueries.get_count(
            QueryDict('tcount=5'), param_name='tcount'), 5)

        searchqueries.get_count(QueryDict('count=1001'), max=1050)

        self.assertEquals(searchqueries.get_count(QueryDict(''), default=5), 5)

    def test_get_skip(self):
        self.assertEquals(searchqueries.get_skip(QueryDict('skip=5')), 5)

        with self.assertRaises(QueryException):
            searchqueries.get_skip(QueryDict('skip=-1'))

        with self.assertRaises(QueryException):
            searchqueries.get_skip(QueryDict('skip=test'))

        self.assertEquals(searchqueries.get_skip(
            QueryDict('tskip=5'), param_name='tskip'), 5)

        self.assertEquals(searchqueries.get_skip(
            QueryDict('')), searchqueries._DEFAULT_SKIP)

        self.assertEquals(searchqueries.get_skip(QueryDict(''), default=5), 5)

    def test_get_return_objects(self):
        self.assertTrue(searchqueries.get_return_objects(
            QueryDict('objects=true')))
        self.assertTrue(searchqueries.get_return_objects(
            QueryDict('objects=TRUE')))
        self.assertFalse(searchqueries.get_return_objects(
            QueryDict('objects=false')))
        self.assertFalse(searchqueries.get_return_objects(
            QueryDict('objects=FALSE')))

        self.assertEquals(searchqueries.get_return_objects(
            QueryDict('')), searchqueries._DEFAULT_RETURN_OBJECTS)

        self.assertEquals(searchqueries.get_return_objects(
            QueryDict('tobjects=true'), param_name='tobjects'), True)
        self.assertEquals(searchqueries.get_return_objects(
            QueryDict('tobjects=false'), param_name='tobjects'), False)

        self.assertEquals(searchqueries.get_return_objects(
            QueryDict(''), default=True), True)
        self.assertEquals(searchqueries.get_return_objects(
            QueryDict(''), default=False), False)

    def test_return_total_count(self):
        self.assertTrue(searchqueries.get_return_total_count(
            QueryDict('totalcount=true')))
        self.assertTrue(searchqueries.get_return_total_count(
            QueryDict('totalcount=TRUE')))
        self.assertFalse(searchqueries.get_return_total_count(
            QueryDict('totalcount=false')))
        self.assertFalse(searchqueries.get_return_total_count(
            QueryDict('totalcount=FALSE')))

        self.assertEquals(searchqueries.get_return_total_count(
            QueryDict('')), searchqueries._DEFAULT_RETURN_TOTAL_COUNT)

        self.assertEquals(searchqueries.get_return_total_count(
            QueryDict('ttotalcount=true'), param_name='ttotalcount'), True)
        self.assertEquals(searchqueries.get_return_total_count(
            QueryDict('ttotalcount=false'), param_name='ttotalcount'), False)

        self.assertEquals(searchqueries.get_return_total_count(
            QueryDict(''), default=True), True)
        self.assertEquals(searchqueries.get_return_total_count(
            QueryDict(''), default=False), False)

    @staticmethod
    def _to_sort(object_name, sort, default_sort_enabled):
        sort_list = searchqueries.sortutils.to_sort_list(
            object_name, sort, default_sort_enabled)
        db_sort_list = searchqueries.sortutils.sort_list_to_db_sort_list(
            object_name, sort_list)

        sort = searchqueries.sortutils.to_order_by_fields(db_sort_list)

        return sort

    def test_get_sort(self):
        self.assertEquals(searchqueries.get_sort(
            QueryDict(''), 'feed'), SearchQueriesTestCase._to_sort('feed', '', True))

        self.assertEquals(searchqueries.get_sort(QueryDict(
            'sort=title:ASC'), 'feed'), SearchQueriesTestCase._to_sort('feed', 'title:ASC', True))

        self.assertEquals(searchqueries.get_sort(QueryDict('tsort=title:ASC'), 'feed',
                                                 param_name='tsort'), SearchQueriesTestCase._to_sort('feed', 'title:ASC', True))

        self.assertEquals(searchqueries.get_sort(QueryDict(
            '_disabledefaultsort=true'), 'feed'), SearchQueriesTestCase._to_sort('feed', '', False))
        self.assertEquals(searchqueries.get_sort(QueryDict(
            '_disabledefaultsort=TRUE'), 'feed'), SearchQueriesTestCase._to_sort('feed', '', False))
        self.assertEquals(searchqueries.get_sort(QueryDict(
            '_disabledefaultsort=false'), 'feed'), SearchQueriesTestCase._to_sort('feed', '', True))
        self.assertEquals(searchqueries.get_sort(QueryDict(
            '_disabledefaultsort=FALSE'), 'feed'), SearchQueriesTestCase._to_sort('feed', '', True))

        self.assertEquals(searchqueries.get_sort(QueryDict('t_disabledefaultsort=true'), 'feed',
                                                 disable_default_sort_param_name='t_disabledefaultsort'), SearchQueriesTestCase._to_sort('feed', '', False))

    def test_get_search(self):
        self.assertEquals(searchqueries.get_search(
            Context(), QueryDict(''), 'user'), [])
        self.assertEquals(searchqueries.get_search(Context(), QueryDict('search=email:"test"'),
                                                   'user'), searchqueries.searchutils.to_filter_args('user', Context(), 'email:"test"'))

        self.assertEquals(searchqueries.get_search(Context(), QueryDict('tsearch=email:"test"'), 'user',
                                                   param_name='tsearch'), searchqueries.searchutils.to_filter_args('user', Context(), 'email:"test"'))

    def test_get_field_maps(self):
        self.assertEquals(searchqueries.get_field_maps(QueryDict(
            ''), 'feed'), searchqueries.fieldutils.get_default_field_maps('feed'))

        self.assertEquals(searchqueries.get_field_maps(QueryDict('fields=uuid'), 'feed'),
                          [searchqueries.fieldutils.to_field_map('feed', 'uuid')])

        self.assertEquals(searchqueries.get_field_maps(QueryDict('fields=uuid,title'), 'feed'),
                          [searchqueries.fieldutils.to_field_map('feed', 'uuid'), searchqueries.fieldutils.to_field_map('feed', 'title')])

        with self.settings(DEBUG=True):
            self.assertEquals(searchqueries.get_field_maps(QueryDict('fields=_all'), 'feed'),
                              searchqueries.fieldutils.get_all_field_maps('feed'))

        self.assertEquals(searchqueries.get_field_maps(QueryDict(
            'fields=badField'), 'feed'), searchqueries.fieldutils.get_default_field_maps('feed'))

        self.assertEquals(searchqueries.get_field_maps(QueryDict('tfields=uuid'), 'feed', param_name='tfields'),
                          [searchqueries.fieldutils.to_field_map('feed', 'uuid')])

    def test_generate_return_object(self):
        field_maps = [
            {
                'field_name': 'uuid',
                'accessor': lambda context, db_obj: db_obj.uuid,
            }
        ]

        class MockObject:
            pass

        db_obj = MockObject()
        db_obj.uuid = 'test string'

        context = Context()

        self.assertEquals(searchqueries.generate_return_object(field_maps, db_obj, context), {
            'uuid': 'test string',
        })
