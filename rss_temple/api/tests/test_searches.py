import logging
import uuid

from django.test import TestCase

from api import searches, models
from api.exceptions import QueryException
from api.context import Context


class SearchesTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)

    def test_standard(self):
        searches.to_filter_args('feed', Context(
        ), 'uuid:"99d63124-59e2-4204-ba61-be294dcb4d22,c54a1f76-f350-4336-b7c4-33ec8f5e81a3"')

    def test_malformed(self):
        with self.assertRaises(QueryException):
            searches.to_filter_args('user', Context(), '')

        with self.assertRaises(QueryException):
            searches.to_filter_args('user', Context(), '((email:"test")')

    def test_unknown_field(self):
        with self.assertRaises(QueryException):
            searches.to_filter_args('feed', Context(), 'email:"test"')

    def test_malformed_value(self):
        with self.assertRaises(QueryException):
            searches.to_filter_args('feed', Context(), 'uuid:"bad uuid"')

    def test_and(self):
        searches.to_filter_args(
            'user', Context(), 'email:"test" or email:"example"')
        searches.to_filter_args(
            'user', Context(), 'email:"test" OR email:"example"')

    def test_or(self):
        searches.to_filter_args(
            'user', Context(), 'email:"test" and email:"example"')
        searches.to_filter_args(
            'user', Context(), 'email:"test" AND email:"example"')

    def test_parenthesized(self):
        searches.to_filter_args(
            'user', Context(), 'email:"word" or (email:"test" and email:"example")')
        searches.to_filter_args(
            'user', Context(), 'email:"test" or (email:"example")')
        searches.to_filter_args('user', Context(), '(email:"test")')
        searches.to_filter_args('user', Context(), '((email:"test"))')

    def test_exclude(self):
        searches.to_filter_args('feed', Context(
        ), 'uuid:!"99d63124-59e2-4204-ba61-be294dcb4d22,c54a1f76-f350-4336-b7c4-33ec8f5e81a3"')


class AllSearchesTestCase(TestCase):
    TRIALS = {
        'user': {
            'get_queryset': lambda: models.User.objects,
            'searches': {
                'uuid': [str(uuid.uuid4())],
                'email': ['test@test.com'],
                'email_exact': ['test@test.com'],
            },
        },
        'usercategory': {
            'get_queryset': lambda: models.UserCategory.objects,
            'searches': {
                'uuid': [str(uuid.uuid4())],
                'text': ['test'],
                'text_exact': ['test'],
            },
        },
        'feed': {
            'get_queryset': lambda: models.Feed.objects.with_subscription_data(AllSearchesTestCase.user),
            'searches': {
                'uuid': [str(uuid.uuid4())],
                'title': ['test'],
                'title_exact': ['test'],
                'feedUrl': ['http://example.com/rss.xml'],
                'homeUrl': ['http://example.com'],
                'publishedAt': ['2018-11-23|2018-11-26'],
                'publishedAt_exact': ['2018-11-26'],
                'publishedAt_delta': ['yesterday'],
                'updatedAt': ['2018-11-23|2018-11-26'],
                'updatedAt_exact': ['2018-11-26'],
                'updatedAt_delta': ['yesterday'],
                'subscribed': ['true', 'false'],

                'customTitle': ['custom title'],
                'customTitle_exact': ['custom title'],
                'customTitle_null': ['true', 'false'],
                'calculatedTitle': ['calculated title'],
                'calculatedTitle_exact': ['calculated title'],
            },
        },
        'feedentry': {
            'get_queryset': lambda: models.FeedEntry.objects,
            'searches': {
                'uuid': [str(uuid.uuid4())],
                'feedUuid': [str(uuid.uuid4())],
                'feedUrl': ['http://example.com/rss.xml'],
                'createdAt': ['2018-11-23|2018-11-26'],
                'createdAt_exact': ['2018-11-26'],
                'createdAt_delta': ['yesterday'],
                'publishedAt': ['2018-11-23|2018-11-26'],
                'publishedAt_exact': ['2018-11-26'],
                'publishedAt_delta': ['yesterday'],
                'updatedAt': ['2018-11-23|2018-11-26'],
                'updatedAt_exact': ['2018-11-26'],
                'updatedAt_delta': ['yesterday'],
                'url': ['http://example.com/entry1.html'],
                'authorName': ['John Doe'],
                'authorName_exact': ['John Doe'],

                'subscribed': ['true', 'false'],
                'isRead': ['true', 'false'],
                'isFavorite': ['true', 'false'],
            },
        },
    }

    class MockRequest:
        def __init__(self):
            self.user = AllSearchesTestCase.user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)

        cls.user = models.User.objects.create(
            email='test_searches@test.com')

    def test_run(self):
        self.assertEqual(len(AllSearchesTestCase.TRIALS),
                         len(searches._search_fns))

        for key, trial_dict in AllSearchesTestCase.TRIALS.items():
            search_fns_dict = searches._search_fns[key]

            trial_searches = trial_dict['searches']
            self.assertEqual(len(trial_searches), len(search_fns_dict))

            queryset = trial_dict['get_queryset']()

            for field, test_values in trial_searches.items():
                for test_value in test_values:
                    context = Context()

                    context.request = AllSearchesTestCase.MockRequest()

                    q = search_fns_dict[field](context, test_value)
                    result = list(queryset.filter(q))

                    self.assertIsNotNone(result)
