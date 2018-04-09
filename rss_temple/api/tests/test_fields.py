from unittest import TestCase

from api import fields

class FieldsTestCase(TestCase):
    def test_default_field_maps(self):
        default_field_maps = fields.get_default_field_maps('feed')

        self.assertEquals(len(default_field_maps), 1)

        for field_map in default_field_maps:
            self.assertIn('field_name', field_map)
            self.assertIsInstance(field_map['field_name'], str)
            self.assertIn('accessor', field_map)
            self.assertIs(callable(field_map['accessor']), True)

    def test_all_field_maps(self):
        all_field_maps = fields.get_all_field_maps('feed')

        self.assertEquals(len(all_field_maps), 6)

        for field_map in all_field_maps:
            self.assertIn('field_name', field_map)
            self.assertIsInstance(field_map['field_name'], str)
            self.assertIn('accessor', field_map)
            self.assertIs(callable(field_map['accessor']), True)
