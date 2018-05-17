import uuid

from django.test import TestCase

from api import fields

class FieldsTestCase(TestCase):
    def test_default_field_maps(self):
        default_field_maps = fields.get_default_field_maps('feed')

        self.assertEquals(len(default_field_maps), 1)

        for field_map in default_field_maps:
            self.assertIn('field_name', field_map)
            self.assertIsInstance(field_map['field_name'], str)
            self.assertIn('accessor', field_map)
            self.assertTrue(callable(field_map['accessor']))

    def test_all_field_maps(self):
        all_field_maps = fields.get_all_field_maps('feed')

        self.assertEquals(len(all_field_maps), 6)

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
        field_map = fields.to_field_map('feed', 'uuid')

        self.assertEquals(field_map['field_name'], 'uuid')

        class TestContext:
            pass

        class TestObject:
            def __init__(self):
                self.uuid = uuid.uuid4()

        test_context = TestContext()
        test_obj = TestObject()
        self.assertIsInstance(field_map['accessor'](test_context, test_obj), str)

        field_map = fields.to_field_map('feed', 'bad_field_name')
        self.assertIsNone(field_map)
