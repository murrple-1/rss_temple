from unittest import TestCase

from api import sorts

class SortsTestCase(TestCase):
    @staticmethod
    def _to_sort(object_name, sort, default_sort_enabled):
        sort_list = sorts.to_sort_list(object_name, sort, default_sort_enabled)
        db_sort_list = sorts.sort_list_to_db_sort_list(object_name, sort_list)

        sort = sorts.to_order_by_fields(db_sort_list)

        return sort

    def test_default(self):
        sort = SortsTestCase._to_sort('channel', 'name:ASC', True)

        self.assertEqual(sort, ['name', 'uuid'])

    def test_nondefault(self):
        sort = SortsTestCase._to_sort('channel', 'name:ASC', False)

        self.assertEqual(sort, ['name'])

    def test_multiple_default(self):
        sort = SortsTestCase._to_sort('channel', 'name:ASC,homeLink:ASC', True)

        self.assertEqual(sort, ['name', 'home_link', 'uuid'])

    def test_multiple_nondefault(self):
        sort = SortsTestCase._to_sort('channel', 'name:ASC,homeLink:ASC', False)

        self.assertEqual(sort, ['name', 'home_link'])

    def test_descending_default(self):
        sort = SortsTestCase._to_sort('channel', 'name:DESC', True)

        self.assertEqual(sort, ['-name', 'uuid'])

    def test_descending_nondefault(self):
        sort = SortsTestCase._to_sort('channel', 'name:DESC', False)

        self.assertEqual(sort, ['-name'])

    def test_multiple_descending_default(self):
        sort = SortsTestCase._to_sort('channel', 'name:DESC,homeLink:DESC', True)

        self.assertEqual(sort, ['-name', '-home_link', 'uuid'])

    def test_multiple_descending_nondefault(self):
        sort = SortsTestCase._to_sort('channel', 'name:DESC,homeLink:DESC', False)

        self.assertEqual(sort, ['-name', '-home_link'])

    def test_multiple_mixed_default(self):
        sort = SortsTestCase._to_sort('channel', 'name:DESC,homeLink:ASC', True)

        self.assertEqual(sort, ['-name', 'home_link', 'uuid'])

    def test_multiple_mixed_nondefault(self):
        sort = SortsTestCase._to_sort('channel', 'name:DESC,homeLink:ASC', False)

        self.assertEqual(sort, ['-name', 'home_link'])

    def test_multiple_overwritedefault(self):
        sort = SortsTestCase._to_sort('channel', 'uuid:ASC,name:DESC', True)

        self.assertEqual(sort, ['uuid', '-name'])
