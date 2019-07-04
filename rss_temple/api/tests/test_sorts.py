from django.test import TestCase

from api import sorts, models
from api.exceptions import QueryException


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

    def test_sort_malformed(self):
        with self.assertRaises(QueryException):
            sorts.to_sort_list('feed', 'bad sort string', True)

    def test_default_descriptor_errors(self):
        with self.assertRaises(TypeError):
            sorts._DefaultDescriptor(None, 'DESC')

        with self.assertRaises(ValueError):
            sorts._DefaultDescriptor(0, None)

        with self.assertRaises(ValueError):
            sorts._DefaultDescriptor(0, 'BAD')

    def test_sort_config_errors(self):
        with self.assertRaises(TypeError):
            sorts._SortConfig(None, None)

        with self.assertRaises(TypeError):
            sorts._SortConfig('testField', None)

        with self.assertRaises(TypeError):
            sorts._SortConfig([None], None)

        with self.assertRaises(TypeError):
            sorts._SortConfig(['testField'], object())

        with self.assertRaises(ValueError):
            sorts._SortConfig([], None)

    def test_bad_sort_list(self):
        with self.assertRaises(QueryException):
            sorts.sort_list_to_db_sort_list('user', [
                {
                    'field_name': 'bad_field',
                    'direction': 'ASC',
                }
            ])


class AllSortsTestCase(TestCase):
    TRIALS = {
        'user': {
            'get_queryset': lambda: models.User.objects,
        },
        'usercategory': {
            'get_queryset': lambda: models.UserCategory.objects,
        },
        'feed': {
            'get_queryset': lambda: models.Feed.objects.with_subscription_data(AllSortsTestCase.user),
        },
        'feedentry': {
            'get_queryset': lambda: models.FeedEntry.objects,
        },
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        models.User.objects.all().delete()

        cls.user = models.User.objects.create(
            email='test_searches@test.com')

    def test_run(self):
        self.assertEqual(len(AllSortsTestCase.TRIALS), len(sorts._sort_configs))

        for key, trial_dict in AllSortsTestCase.TRIALS.items():
            sorts_dict = sorts._sort_configs[key]

            sort_keys = sorts_dict.keys()

            sort_list = sorts.to_sort_list(key, ','.join(f'{sort_key}:ASC' for sort_key in sort_keys), False)

            db_sort_list = sorts.sort_list_to_db_sort_list(key, sort_list)

            sort = sorts.to_order_by_fields(db_sort_list)

            result = list(trial_dict['get_queryset']().order_by(*sort))

            self.assertIsNotNone(result)
