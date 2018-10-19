import uuid

from django.test import TestCase

from api import fields


class _ObjectConfig:
    def __init__(self, object_name, all_count, default_count, good_field_name, bad_field_name='bad_field_name'):
        self.object_name = object_name
        self.all_count = all_count
        self.default_count = default_count
        self.good_field_name = good_field_name
        self.bad_field_name = bad_field_name


_object_configs = [
    _ObjectConfig('user', 3, 1, 'uuid'),
    _ObjectConfig('feed', 7, 1, 'uuid'),
    _ObjectConfig('feedentry', 11, 1, 'uuid'),
]

class FieldsTestCase(TestCase):
    def test_default_field_maps(self):
        for oc in _object_configs:
            default_field_maps = fields.get_default_field_maps(oc.object_name)

            self.assertEquals(len(default_field_maps), oc.default_count)

            for field_map in default_field_maps:
                self.assertIn('field_name', field_map)
                self.assertIsInstance(field_map['field_name'], str)
                self.assertIn('accessor', field_map)
                self.assertTrue(callable(field_map['accessor']))

    def test_all_field_maps(self):
        for oc in _object_configs:
            all_field_maps = fields.get_all_field_maps(oc.object_name)

            self.assertEquals(len(all_field_maps), oc.all_count)

            for field_map in all_field_maps:
                self.assertIn('field_name', field_map)
                self.assertIsInstance(field_map['field_name'], str)
                self.assertIn('accessor', field_map)
                self.assertTrue(callable(field_map['accessor']))

    def test_fieldconfig(self):
        fc = fields._FieldConfig(lambda context, db_obj: 'test', True)

        self.assertEquals(fc.accessor(object(), object()), 'test')
        self.assertTrue(fc.default)

        with self.assertRaises(TypeError):
            fields._FieldConfig(None, None)

        with self.assertRaises(TypeError):
            fields._FieldConfig(lambda: None, None)

    def test_to_field_map(self):
        for oc in _object_configs:
            field_map = fields.to_field_map(oc.object_name, oc.good_field_name)

            self.assertEquals(field_map['field_name'], oc.good_field_name)

            class TestContext:
                pass

            class TestObject:
                def __init__(self):
                    self.uuid = uuid.uuid4()

            test_context = TestContext()
            test_obj = TestObject()
            self.assertIsInstance(field_map['accessor'](
                test_context, test_obj), str)

            field_map = fields.to_field_map(oc.object_name, oc.bad_field_name)
            self.assertIsNone(field_map)
