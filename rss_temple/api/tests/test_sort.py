from unittest import TestCase

from api import sorts

class SortTestCase(TestCase):
    @staticmethod
    def _to_sort(object_name, sort, default_sort_enabled):
        sort_list = sorts.to_sort_list(object_name, sort, default_sort_enabled)
        db_sort_list = sorts.sort_list_to_db_sort_list(object_name, sort_list)

        sort = sorts.to_order_by_fields(db_sort_list)

        return sort

    def test_default(self):
        sort = SortTestCase._to_sort('channel', 'name:ASC', True)

        self.assertEqual(sort, ['name', 'uuid'])

    def test_nondefault(self):
        sort = SortTestCase._to_sort('channel', 'name:ASC', False)

        self.assertEqual(sort, ['name'])

    def test_multiple_default(self):
        sort = SortTestCase._to_sort('channel', 'name:ASC,link:ASC', True)

        self.assertEqual(sort, ['name', 'link', 'uuid'])

    def test_multiple_nondefault(self):
        sort = SortTestCase._to_sort('channel', 'name:ASC,link:ASC', False)

        self.assertEqual(sort, ['name', 'link'])

    def test_descending_default(self):
        sort = SortTestCase._to_sort('channel', 'name:DESC', True)

        self.assertEqual(sort, ['-name', 'uuid'])

    def test_descending_nondefault(self):
        sort = SortTestCase._to_sort('channel', 'name:DESC', False)

        self.assertEqual(sort, ['-name'])

    def test_multiple_descending_default(self):
        sort = SortTestCase._to_sort('channel', 'name:DESC,link:DESC', True)

        self.assertEqual(sort, ['-name', '-link', 'uuid'])

    def test_multiple_descending_nondefault(self):
        sort = SortTestCase._to_sort('channel', 'name:DESC,link:DESC', False)

        self.assertEqual(sort, ['-name', '-link'])

    def test_multiple_mixed_default(self):
        sort = SortTestCase._to_sort('channel', 'name:DESC,link:ASC', True)

        self.assertEqual(sort, ['-name', 'link', 'uuid'])

    def test_multiple_mixed_nondefault(self):
        sort = SortTestCase._to_sort('channel', 'name:DESC,link:ASC', False)

        self.assertEqual(sort, ['-name', 'link'])

    def test_multiple_overwritedefault(self):
        sort = SortTestCase._to_sort('channel', 'uuid:ASC,name:DESC', True)

        self.assertEqual(sort, ['uuid', '-name'])
