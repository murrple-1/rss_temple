import uuid
from unittest.mock import Mock

from django.http import HttpRequest
from django.test import SimpleTestCase

from query_utils import fields as fieldutils

field_configs: dict[str, dict[str, fieldutils.FieldConfig]] = {
    "object": {
        "uuid": fieldutils.FieldConfig(
            lambda request, db_obj, queryset: str(db_obj.uuid),
            True,
            {"uuid"},
        ),
        "text": fieldutils.FieldConfig(
            lambda request, db_obj, queryset: db_obj.text,
            False,
            {"text"},
        ),
    },
}


class FieldsTestCase(SimpleTestCase):
    def test_default_field_maps(self):
        default_field_maps = fieldutils.get_default_field_maps("object", field_configs)

        self.assertEqual(len(default_field_maps), 1)

        for field_map in default_field_maps:
            self.assertIn("field_name", field_map)
            self.assertIs(type(field_map["field_name"]), str)
            self.assertIn("accessor", field_map)
            self.assertTrue(callable(field_map["accessor"]))

    def test_all_field_maps(self):
        all_field_maps = fieldutils.get_all_field_maps("object", field_configs)

        self.assertEqual(len(all_field_maps), 2)

        for field_map in all_field_maps:
            self.assertIn("field_name", field_map)
            self.assertIs(type(field_map["field_name"]), str)
            self.assertIn("accessor", field_map)
            self.assertTrue(callable(field_map["accessor"]))

    def test_fieldconfig(self):
        fc = fieldutils.FieldConfig(
            lambda request, db_obj, queryset: "test", True, {"field_name"}
        )

        db_obj = object()
        queryset = [db_obj]
        self.assertEqual(fc.accessor(Mock(HttpRequest), db_obj, queryset), "test")
        self.assertTrue(fc.default)

    def test_to_field_map(self):
        field_map = fieldutils.to_field_map("object", "uuid", field_configs)

        assert field_map is not None

        self.assertEqual(field_map["field_name"], "uuid")

        class TestObject:
            def __init__(self):
                self.uuid = uuid.uuid4()

        db_obj = TestObject()
        queryset = [db_obj]

        field_map["accessor"](Mock(HttpRequest), db_obj, queryset)

        field_map = fieldutils.to_field_map("object", "badfield", field_configs)
        self.assertIsNone(field_map)

    def test_generate_return_object(self):
        field_maps: list[fieldutils.FieldMap] = [
            {
                "field_name": "uuid",
                "accessor": lambda request, db_obj, queryset: db_obj.uuid,
                "only_fields": {"uuid"},
            }
        ]

        db_obj = Mock()
        db_obj.uuid = "test string"

        queryset = [db_obj]

        self.assertEqual(
            fieldutils.generate_return_object(
                field_maps, db_obj, Mock(HttpRequest), queryset
            ),
            {
                "uuid": "test string",
            },
        )

    def test_generate_only_fields(self):
        field_maps: list[fieldutils.FieldMap] = [
            {
                "field_name": "myUuid",
                "accessor": lambda request, db_obj, queryset: db_obj.uuid,
                "only_fields": {"uuid"},
            },
            {
                "field_name": "myText",
                "accessor": lambda request, db_obj, queryset: db_obj.text,
                "only_fields": {"text"},
            },
        ]

        self.assertEqual(
            fieldutils.generate_only_fields(field_maps),
            {"uuid", "text"},
        )

    def test_generate_field_names(self):
        field_maps: list[fieldutils.FieldMap] = [
            {
                "field_name": "myUuid",
                "accessor": lambda request, db_obj, queryset: db_obj.uuid,
                "only_fields": {"uuid"},
            },
            {
                "field_name": "myText",
                "accessor": lambda request, db_obj, queryset: db_obj.text,
                "only_fields": {"text"},
            },
        ]

        self.assertEqual(
            fieldutils.generate_field_names(field_maps),
            {"myUuid", "myText"},
        )
