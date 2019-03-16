import datetime
from decimal import Decimal

from django.test import TestCase
from django.http.request import QueryDict

from api import query_utils
from api.exceptions import QueryException
from api.context import Context


class QueryUtilsTestCase(TestCase):
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
        content, content_type = query_utils.serialize_content({
            'test1': 1,
            'test2': True
        })

        self.assertEquals(content_type, 'application/json')
        self.assertEquals(content, '{"test1":1,"test2":true}')

    def test_get_count(self):
        self.assertEquals(query_utils.get_count({
            'count': 5,
        }), 5)

        with self.assertRaises(QueryException):
            query_utils.get_count({
                'count': -1,
            })

        with self.assertRaises(QueryException):
            query_utils.get_count({
                'count': 1001,
            })

        with self.assertRaises(QueryException):
            query_utils.get_count({
                'count': 'test',
            })

        self.assertEquals(query_utils.get_count({}),
                          query_utils._DEFAULT_COUNT)

        self.assertEquals(query_utils.get_count({
            'tcount': 5,
        }, param_name='tcount'), 5)

        query_utils.get_count({
            'count': 1001,
        }, max_=1050)

        self.assertEquals(query_utils.get_count({}, default=5), 5)

    def test_get_skip(self):
        self.assertEquals(query_utils.get_skip({
            'skip': 5,
        }), 5)

        with self.assertRaises(QueryException):
            query_utils.get_skip({
                'skip': -1,
            })

        with self.assertRaises(QueryException):
            query_utils.get_skip({
                'skip': 'test',
            })

        self.assertEquals(query_utils.get_skip({
            'tskip': 5,
        }, param_name='tskip'), 5)

        self.assertEquals(query_utils.get_skip(
            {}), query_utils._DEFAULT_SKIP)

        self.assertEquals(query_utils.get_skip({}, default=5), 5)

    def test_get_return_objects(self):
        self.assertTrue(query_utils.get_return_objects(
            {
                'objects': True,
            }))
        self.assertFalse(query_utils.get_return_objects(
            {
                'objects': False,
            }))

        self.assertEquals(query_utils.get_return_objects({}),
                          query_utils._DEFAULT_RETURN_OBJECTS)

        self.assertEquals(query_utils.get_return_objects(
            {
                'tobjects': True,
            }, param_name='tobjects'), True)
        self.assertEquals(query_utils.get_return_objects(
            {
                'tobjects': False,
            }, param_name='tobjects'), False)

        self.assertEquals(
            query_utils.get_return_objects({}, default=True), True)
        self.assertEquals(query_utils.get_return_objects(
            {}, default=False), False)

    def test_return_total_count(self):
        self.assertTrue(query_utils.get_return_total_count(
            {
                'totalCount': True,
            }))
        self.assertFalse(query_utils.get_return_total_count(
            {
                'totalCount': False,
            }))

        self.assertEquals(query_utils.get_return_total_count(
            {}), query_utils._DEFAULT_RETURN_TOTAL_COUNT)

        self.assertEquals(query_utils.get_return_total_count(
            {
                't_totalCount': True,
            }, param_name='t_totalCount'), True)
        self.assertEquals(query_utils.get_return_total_count(
            {
                't_totalCount': False,
            }, param_name='t_totalCount'), False)

        self.assertEquals(query_utils.get_return_total_count(
            {}, default=True), True)
        self.assertEquals(query_utils.get_return_total_count(
            {}, default=False), False)

    @staticmethod
    def _to_sort(object_name, sort, default_sort_enabled):
        sort_list = query_utils.sortutils.to_sort_list(
            object_name, sort, default_sort_enabled)
        db_sort_list = query_utils.sortutils.sort_list_to_db_sort_list(
            object_name, sort_list)

        sort = query_utils.sortutils.to_order_by_fields(db_sort_list)

        return sort

    def test_get_sort(self):
        self.assertEquals(query_utils.get_sort(
            {}, 'feed'), QueryUtilsTestCase._to_sort('feed', '', True))

        self.assertEquals(query_utils.get_sort({
            'sort': 'title:ASC',
        }, 'feed'), QueryUtilsTestCase._to_sort('feed', 'title:ASC', True))

        self.assertEquals(query_utils.get_sort({
            'tsort': 'title:ASC',
        }, 'feed', param_name='tsort'), QueryUtilsTestCase._to_sort('feed', 'title:ASC', True))

        self.assertEquals(query_utils.get_sort({
            'disableDefaultSort': True,
        }, 'feed'), QueryUtilsTestCase._to_sort('feed', '', False))
        self.assertEquals(query_utils.get_sort({
            'disableDefaultSort': False,
        }, 'feed'), QueryUtilsTestCase._to_sort('feed', '', True))

        self.assertEquals(query_utils.get_sort({
            't_disableDefaultSort': True,
        }, 'feed', disable_default_sort_param_name='t_disableDefaultSort'), QueryUtilsTestCase._to_sort('feed', '', False))

    def test_get_search(self):
        self.assertEquals(query_utils.get_search(
            Context(), {}, 'user'), [])
        self.assertEquals(query_utils.get_search(Context(), {
            'search': 'email:"test"',
        }, 'user'), query_utils.searchutils.to_filter_args('user', Context(), 'email:"test"'))

        self.assertEquals(query_utils.get_search(Context(), {
            'tsearch': 'email:"test"',
        }, 'user', param_name='tsearch'), query_utils.searchutils.to_filter_args('user', Context(), 'email:"test"'))

    def test_get_fields__query_dict(self):
        self.assertEquals(
            query_utils.get_fields__query_dict(QueryDict('')), [])
        self.assertEquals(query_utils.get_fields__query_dict(
            QueryDict('fields=uuid,name')), ['uuid', 'name'])
        self.assertEquals(query_utils.get_fields__query_dict(
            QueryDict('tfields=uuid,name'), param_name='tfields'), ['uuid', 'name'])

    def test_get_fields__json(self):
        self.assertEquals(query_utils.get_fields__json({}), [])
        self.assertEquals(query_utils.get_fields__json({
            'fields': ['uuid', 'name'],
        }), ['uuid', 'name'])
        self.assertEquals(query_utils.get_fields__json({
            'tfields': ['uuid', 'name'],
        }, param_name='tfields'), ['uuid', 'name'])

    def test_get_field_maps(self):
        self.assertEquals(query_utils.get_field_maps(
            [], 'feed'), query_utils.fieldutils.get_default_field_maps('feed'))

        self.assertEquals(query_utils.get_field_maps(['uuid'], 'feed'), [
                          query_utils.fieldutils.to_field_map('feed', 'uuid')])

        self.assertEquals(query_utils.get_field_maps(['uuid', 'title'], 'feed'),
                          [query_utils.fieldutils.to_field_map('feed', 'uuid'), query_utils.fieldutils.to_field_map('feed', 'title')])

        with self.settings(DEBUG=True):
            self.assertEquals(query_utils.get_field_maps(['_all'], 'feed'),
                              query_utils.fieldutils.get_all_field_maps('feed'))

        self.assertEquals(query_utils.get_field_maps(
            ['badField'], 'feed'), query_utils.fieldutils.get_default_field_maps('feed'))

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

        self.assertEquals(query_utils.generate_return_object(field_maps, db_obj, context), {
            'uuid': 'test string',
        })
