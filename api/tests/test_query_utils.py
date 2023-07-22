from unittest.mock import Mock

from django.http import HttpRequest
from django.http.request import QueryDict
from django.test import TestCase

from api import query_utils
from api.exceptions import QueryException
from api.fields import FieldMap


class QueryUtilsTestCase(TestCase):
    def test_get_count(self):
        self.assertEqual(
            query_utils.get_count(
                {
                    "count": 5,
                }
            ),
            5,
        )

        with self.assertRaises(QueryException):
            query_utils.get_count(
                {
                    "count": -1,
                }
            )

        with self.assertRaises(QueryException):
            query_utils.get_count(
                {
                    "count": 1001,
                }
            )

        with self.assertRaises(QueryException):
            query_utils.get_count(
                {
                    "count": "test",
                }
            )

        self.assertEqual(query_utils.get_count({}), query_utils._DEFAULT_COUNT)

        self.assertEqual(
            query_utils.get_count(
                {
                    "tcount": 5,
                },
                param_name="tcount",
            ),
            5,
        )

        query_utils.get_count(
            {
                "count": 1001,
            },
            max_=1050,
        )

        self.assertEqual(query_utils.get_count({}, default=5), 5)

    def test_get_skip(self):
        self.assertEqual(
            query_utils.get_skip(
                {
                    "skip": 5,
                }
            ),
            5,
        )

        with self.assertRaises(QueryException):
            query_utils.get_skip(
                {
                    "skip": -1,
                }
            )

        with self.assertRaises(QueryException):
            query_utils.get_skip(
                {
                    "skip": "test",
                }
            )

        self.assertEqual(
            query_utils.get_skip(
                {
                    "tskip": 5,
                },
                param_name="tskip",
            ),
            5,
        )

        self.assertEqual(query_utils.get_skip({}), query_utils._DEFAULT_SKIP)

        self.assertEqual(query_utils.get_skip({}, default=5), 5)

    def test_get_return_objects(self):
        self.assertTrue(
            query_utils.get_return_objects(
                {
                    "objects": True,
                }
            )
        )
        self.assertFalse(
            query_utils.get_return_objects(
                {
                    "objects": False,
                }
            )
        )

        self.assertEqual(
            query_utils.get_return_objects({}), query_utils._DEFAULT_RETURN_OBJECTS
        )

        self.assertEqual(
            query_utils.get_return_objects(
                {
                    "tobjects": True,
                },
                param_name="tobjects",
            ),
            True,
        )
        self.assertEqual(
            query_utils.get_return_objects(
                {
                    "tobjects": False,
                },
                param_name="tobjects",
            ),
            False,
        )

        self.assertEqual(query_utils.get_return_objects({}, default=True), True)
        self.assertEqual(query_utils.get_return_objects({}, default=False), False)

    def test_return_total_count(self):
        self.assertTrue(
            query_utils.get_return_total_count(
                {
                    "totalCount": True,
                }
            )
        )
        self.assertFalse(
            query_utils.get_return_total_count(
                {
                    "totalCount": False,
                }
            )
        )

        self.assertEqual(
            query_utils.get_return_total_count({}),
            query_utils._DEFAULT_RETURN_TOTAL_COUNT,
        )

        self.assertEqual(
            query_utils.get_return_total_count(
                {
                    "t_totalCount": True,
                },
                param_name="t_totalCount",
            ),
            True,
        )
        self.assertEqual(
            query_utils.get_return_total_count(
                {
                    "t_totalCount": False,
                },
                param_name="t_totalCount",
            ),
            False,
        )

        self.assertEqual(query_utils.get_return_total_count({}, default=True), True)
        self.assertEqual(query_utils.get_return_total_count({}, default=False), False)

    @staticmethod
    def _to_order_by_args(object_name, sort, default_sort_enabled):
        sort_list = query_utils.sortutils.to_sort_list(
            object_name, sort, default_sort_enabled
        )
        order_by_args = query_utils.sortutils.sort_list_to_order_by_args(
            object_name, sort_list
        )

        return order_by_args

    def test_get_sort(self):
        self.assertEqual(
            query_utils.get_sort({}, "feed"),
            QueryUtilsTestCase._to_order_by_args("feed", "", True),
        )

        self.assertEqual(
            query_utils.get_sort(
                {
                    "sort": "title:ASC",
                },
                "feed",
            ),
            QueryUtilsTestCase._to_order_by_args("feed", "title:ASC", True),
        )

        self.assertEqual(
            query_utils.get_sort(
                {
                    "tsort": "title:ASC",
                },
                "feed",
                param_name="tsort",
            ),
            QueryUtilsTestCase._to_order_by_args("feed", "title:ASC", True),
        )

        self.assertEqual(
            query_utils.get_sort(
                {
                    "disableDefaultSort": True,
                },
                "feed",
            ),
            QueryUtilsTestCase._to_order_by_args("feed", "", False),
        )
        self.assertEqual(
            query_utils.get_sort(
                {
                    "disableDefaultSort": False,
                },
                "feed",
            ),
            QueryUtilsTestCase._to_order_by_args("feed", "", True),
        )

        self.assertEqual(
            query_utils.get_sort(
                {
                    "t_disableDefaultSort": True,
                },
                "feed",
                disable_default_sort_param_name="t_disableDefaultSort",
            ),
            QueryUtilsTestCase._to_order_by_args("feed", "", False),
        )

    def test_get_search(self):
        self.assertEqual(query_utils.get_search(Mock(HttpRequest), {}, "feed"), [])
        self.assertEqual(
            query_utils.get_search(
                Mock(HttpRequest),
                {
                    "search": 'title:"test"',
                },
                "feed",
            ),
            query_utils.searchutils.to_filter_args(
                "feed", Mock(HttpRequest), 'title:"test"'
            ),
        )

        self.assertEqual(
            query_utils.get_search(
                Mock(HttpRequest),
                {
                    "tsearch": 'title:"test"',
                },
                "feed",
                param_name="tsearch",
            ),
            query_utils.searchutils.to_filter_args(
                "feed", Mock(HttpRequest), 'title:"test"'
            ),
        )

    def test_get_fields__query_dict(self):
        self.assertEqual(query_utils.get_fields__query_dict(QueryDict("", True)), [])
        self.assertEqual(
            query_utils.get_fields__query_dict(QueryDict("fields=uuid,name", True)),
            ["uuid", "name"],
        )
        self.assertEqual(
            query_utils.get_fields__query_dict(
                QueryDict("tfields=uuid,name", True), param_name="tfields"
            ),
            ["uuid", "name"],
        )

    def test_get_fields__json(self):
        self.assertEqual(query_utils.get_fields__json({}), [])
        self.assertEqual(
            query_utils.get_fields__json(
                {
                    "fields": ["uuid", "name"],
                }
            ),
            ["uuid", "name"],
        )
        self.assertEqual(
            query_utils.get_fields__json(
                {
                    "tfields": ["uuid", "name"],
                },
                param_name="tfields",
            ),
            ["uuid", "name"],
        )

    def test_get_field_maps(self):
        self.assertEqual(
            query_utils.get_field_maps([], "feed"),
            query_utils.fieldutils.get_default_field_maps("feed"),
        )

        self.assertEqual(
            query_utils.get_field_maps(["uuid"], "feed"),
            [query_utils.fieldutils.to_field_map("feed", "uuid")],
        )

        self.assertEqual(
            query_utils.get_field_maps(["uuid", "title"], "feed"),
            [
                query_utils.fieldutils.to_field_map("feed", "uuid"),
                query_utils.fieldutils.to_field_map("feed", "title"),
            ],
        )

        with self.settings(DEBUG=True):
            self.assertEqual(
                query_utils.get_field_maps(["_all"], "feed"),
                query_utils.fieldutils.get_all_field_maps("feed"),
            )

        self.assertEqual(
            query_utils.get_field_maps(["badField"], "feed"),
            query_utils.fieldutils.get_default_field_maps("feed"),
        )

    def test_generate_return_object(self):
        field_maps: list[FieldMap] = [
            {
                "field_name": "uuid",
                "accessor": lambda request, db_obj: db_obj.uuid,
            }
        ]

        db_obj = Mock()
        db_obj.uuid = "test string"

        self.assertEqual(
            query_utils.generate_return_object(field_maps, db_obj, Mock(HttpRequest)),
            {
                "uuid": "test string",
            },
        )
