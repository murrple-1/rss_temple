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
        sort = SortsTestCase._to_sort('feed', 'title:ASC', True)

        self.assertEqual(sort, ['title', 'uuid'])

    def test_nondefault(self):
        sort = SortsTestCase._to_sort('feed', 'title:ASC', False)

        self.assertEqual(sort, ['title'])

    def test_multiple_default(self):
        sort = SortsTestCase._to_sort('feed', 'title:ASC,homeUrl:ASC', True)

        self.assertEqual(sort, ['title', 'home_url', 'uuid'])

    def test_multiple_nondefault(self):
        sort = SortsTestCase._to_sort('feed', 'title:ASC,homeUrl:ASC', False)

        self.assertEqual(sort, ['title', 'home_url'])

    def test_descending_default(self):
        sort = SortsTestCase._to_sort('feed', 'title:DESC', True)

        self.assertEqual(sort, ['-title', 'uuid'])

    def test_descending_nondefault(self):
        sort = SortsTestCase._to_sort('feed', 'title:DESC', False)

        self.assertEqual(sort, ['-title'])

    def test_multiple_descending_default(self):
        sort = SortsTestCase._to_sort('feed', 'title:DESC,homeUrl:DESC', True)

        self.assertEqual(sort, ['-title', '-home_url', 'uuid'])

    def test_multiple_descending_nondefault(self):
        sort = SortsTestCase._to_sort('feed', 'title:DESC,homeUrl:DESC', False)

        self.assertEqual(sort, ['-title', '-home_url'])

    def test_multiple_mixed_default(self):
        sort = SortsTestCase._to_sort('feed', 'title:DESC,homeUrl:ASC', True)

        self.assertEqual(sort, ['-title', 'home_url', 'uuid'])

    def test_multiple_mixed_nondefault(self):
        sort = SortsTestCase._to_sort('feed', 'title:DESC,homeUrl:ASC', False)

        self.assertEqual(sort, ['-title', 'home_url'])

    def test_multiple_overwritedefault(self):
        sort = SortsTestCase._to_sort('feed', 'uuid:ASC,title:DESC', True)

        self.assertEqual(sort, ['uuid', '-title'])

    def test_default_descriptor_errors(self):
        with self.assertRaises(TypeError):
            sorts._DefaultDescriptor(None, 'DESC')

        with self.assertRaises(ValueError):
            sorts._DefaultDescriptor(0, None)

        with self.assertRaises(ValueError):
            sorts._DefaultDescriptor(0, 'BAD')
