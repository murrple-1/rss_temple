from unittest import TestCase

from api import models, sorts

class SortTestCase(TestCase):
    def test_default_feed(self):
        sort_list = sorts.to_sort_list('feed', 'name:ASC', True)
        db_sort_list = sorts.sort_list_to_db_sort_list('feed', sort_list)

        sort = sorts.to_order_by_fields(db_sort_list)

        self.assertEqual(sort, ['name', 'uuid'])

    def test_nondefault_feed(self):
        sort_list = sorts.to_sort_list('feed', 'name:ASC', False)
        db_sort_list = sorts.sort_list_to_db_sort_list('feed', sort_list)

        sort = sorts.to_order_by_fields(db_sort_list)

        self.assertEqual(sort, ['name'])

    def test_multiple_default_feed(self):
        sort_list = sorts.to_sort_list('feed', 'name:ASC,link:ASC', True)
        db_sort_list = sorts.sort_list_to_db_sort_list('feed', sort_list)

        sort = sorts.to_order_by_fields(db_sort_list)

        self.assertEqual(sort, ['name', 'link', 'uuid'])

    def test_multiple_nondefault_feed(self):
        sort_list = sorts.to_sort_list('feed', 'name:ASC,link:ASC', False)
        db_sort_list = sorts.sort_list_to_db_sort_list('feed', sort_list)

        sort = sorts.to_order_by_fields(db_sort_list)

        self.assertEqual(sort, ['name', 'link'])

    def test_descending_default_feed(self):
        sort_list = sorts.to_sort_list('feed', 'name:DESC', True)
        db_sort_list = sorts.sort_list_to_db_sort_list('feed', sort_list)

        sort = sorts.to_order_by_fields(db_sort_list)

        self.assertEqual(sort, ['-name', 'uuid'])

    def test_descending_nondefault_feed(self):
        sort_list = sorts.to_sort_list('feed', 'name:DESC', False)
        db_sort_list = sorts.sort_list_to_db_sort_list('feed', sort_list)

        sort = sorts.to_order_by_fields(db_sort_list)

        self.assertEqual(sort, ['-name'])

    def test_multiple_descending_default_feed(self):
        sort_list = sorts.to_sort_list('feed', 'name:DESC,link:DESC', True)
        db_sort_list = sorts.sort_list_to_db_sort_list('feed', sort_list)

        sort = sorts.to_order_by_fields(db_sort_list)

        self.assertEqual(sort, ['-name', '-link', 'uuid'])
