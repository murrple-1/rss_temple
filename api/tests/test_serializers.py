import logging
from typing import ClassVar, cast
from unittest.mock import Mock

from django.http import HttpRequest
from django.test import SimpleTestCase
from rest_framework import serializers

from api.fields import field_configs
from api.searches import search_fns
from api.serializers import GetManySerializer, GetSingleSerializer
from api.sorts import sort_configs
from query_utils import fields as fieldutils
from query_utils import search as searchutils
from query_utils import sort as sortutils


class GetSingleSerializerTestCase(SimpleTestCase):
    def test_fields(self):
        serializer = GetSingleSerializer(
            data={"fields": []}, context={"object_name": "feed"}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            sorted(
                serializer.validated_data["fields"], key=lambda fm: fm["field_name"]
            ),
            sorted(
                fieldutils.get_default_field_maps("feed", field_configs),
                key=lambda fm: fm["field_name"],
            ),
        )

        serializer = GetSingleSerializer(
            data={"fields": ["uuid"]}, context={"object_name": "feed"}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            sorted(
                serializer.validated_data["fields"], key=lambda fm: fm["field_name"]
            ),
            sorted(
                cast(
                    list[fieldutils.FieldMap],
                    [fieldutils.to_field_map("feed", "uuid", field_configs)],
                ),
                key=lambda fm: fm["field_name"],
            ),
        )

        serializer = GetSingleSerializer(
            data={"fields": ["uuid", "title"]}, context={"object_name": "feed"}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            sorted(
                serializer.validated_data["fields"], key=lambda fm: fm["field_name"]
            ),
            sorted(
                cast(
                    list[fieldutils.FieldMap],
                    [
                        fieldutils.to_field_map("feed", "uuid", field_configs),
                        fieldutils.to_field_map("feed", "title", field_configs),
                    ],
                ),
                key=lambda fm: fm["field_name"],
            ),
        )

        with self.settings(DEBUG=True):
            serializer = GetSingleSerializer(
                data={"fields": ["_all"]}, context={"object_name": "feed"}
            )
            serializer.is_valid(raise_exception=True)
            self.assertEqual(
                sorted(
                    serializer.validated_data["fields"], key=lambda fm: fm["field_name"]
                ),
                sorted(
                    fieldutils.get_all_field_maps("feed", field_configs),
                    key=lambda fm: fm["field_name"],
                ),
            )

        serializer = GetSingleSerializer(
            data={"fields": ["badField"]}, context={"object_name": "feed"}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            sorted(
                serializer.validated_data["fields"], key=lambda fm: fm["field_name"]
            ),
            sorted(
                fieldutils.get_default_field_maps("feed", field_configs),
                key=lambda fm: fm["field_name"],
            ),
        )

    def test_fields_typeerror(self):
        serializer = GetSingleSerializer(
            data={"fields": True}, context={"object_name": "feed"}
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

        serializer = GetSingleSerializer(
            data={"fields": [True]}, context={"object_name": "feed"}
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)


class GetManySerializerTestCase(SimpleTestCase):
    old_query_utils_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_query_utils_logger_level = logging.getLogger(
            "rss_temple.query_utils"
        ).getEffectiveLevel()

        logging.getLogger("rss_temple.query_utils").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple.query_utils").setLevel(
            cls.old_query_utils_logger_level
        )

    @staticmethod
    def _to_order_by_args(object_name: str, sort: str, default_sort_enabled: bool):
        sort_list = sortutils.to_sort_list(
            object_name, sort, default_sort_enabled, sort_configs
        )
        order_by_args = sortutils.sort_list_to_order_by_args(
            object_name, sort_list, sort_configs
        )

        return order_by_args

    def test_sort(self):
        serializer = GetManySerializer(data={}, context={"object_name": "feed"})
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            serializer.validated_data["sort"],
            GetManySerializerTestCase._to_order_by_args("feed", "", True),
        )

        serializer = GetManySerializer(
            data={"sort": "title:ASC"}, context={"object_name": "feed"}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            serializer.validated_data["sort"],
            GetManySerializerTestCase._to_order_by_args("feed", "title:ASC", True),
        )

        serializer = GetManySerializer(
            data={"disableDefaultSort": True}, context={"object_name": "feed"}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            serializer.validated_data["sort"],
            GetManySerializerTestCase._to_order_by_args("feed", "", False),
        )

        serializer = GetManySerializer(
            data={"disableDefaultSort": False}, context={"object_name": "feed"}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            serializer.validated_data["sort"],
            GetManySerializerTestCase._to_order_by_args("feed", "", True),
        )

        serializer = GetManySerializer(
            data={"sort": "title:ASC", "disableDefaultSort": True},
            context={"object_name": "feed"},
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            serializer.validated_data["sort"],
            GetManySerializerTestCase._to_order_by_args("feed", "title:ASC", False),
        )

        serializer = GetManySerializer(
            data={"sort": "title:ASC", "disableDefaultSort": False},
            context={"object_name": "feed"},
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            serializer.validated_data["sort"],
            GetManySerializerTestCase._to_order_by_args("feed", "title:ASC", True),
        )

    def test_sort_typeerror(self):
        serializer = GetManySerializer(
            data={
                "sort": True,
            },
            context={"object_name": "feed"},
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_sort_malformed(self):
        serializer = GetManySerializer(
            data={
                "sort": "title",
            },
            context={"object_name": "feed"},
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

        serializer = GetManySerializer(
            data={
                "sort": "title:BAD",
            },
            context={"object_name": "feed"},
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

        serializer = GetManySerializer(
            data={
                "sort": "badField:ASC",
            },
            context={"object_name": "feed"},
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_search(self):
        serializer = GetManySerializer(
            data={}, context={"object_name": "feed", "request": Mock(HttpRequest)}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(serializer.validated_data["search"], [])

        serializer = GetManySerializer(
            data={"search": 'title:"test"'},
            context={"object_name": "feed", "request": Mock(HttpRequest)},
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            serializer.validated_data["search"],
            searchutils.to_filter_args(
                "feed", Mock(HttpRequest), 'title:"test"', search_fns
            ),
        )

    def test_search_typeerror(self):
        serializer = GetManySerializer(
            data={
                "search": True,
            },
            context={"object_name": "feed", "request": Mock(HttpRequest)},
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_search_malformed(self):
        serializer = GetManySerializer(
            data={
                "search": "title",
            },
            context={"object_name": "feed", "request": Mock(HttpRequest)},
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

        serializer = GetManySerializer(
            data={
                "search": "title:BAD",
            },
            context={"object_name": "feed", "request": Mock(HttpRequest)},
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

        serializer = GetManySerializer(
            data={
                "search": "badField:true",
            },
            context={"object_name": "feed", "request": Mock(HttpRequest)},
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)
