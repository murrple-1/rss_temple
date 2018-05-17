import logging

from django.test import TestCase

from api import searches
from api.exceptions import QueryException

class SearchesTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_standard(self):
        searches.to_filter_args('feed', 'uuid:"99d63124-59e2-4204-ba61-be294dcb4d22|c54a1f76-f350-4336-b7c4-33ec8f5e81a3"')

    def test_malformed(self):
        with self.assertRaises(QueryException):
            searches.to_filter_args('user', '')

        with self.assertRaises(QueryException):
            searches.to_filter_args('user', '((email:"test")')

    def test_unknown_field(self):
        with self.assertRaises(QueryException):
            searches.to_filter_args('feed', 'email:"test"')

    def test_malformed_value(self):
        with self.assertRaises(QueryException):
            searches.to_filter_args('feed', 'uuid:"bad uuid"')

    def test_and(self):
        searches.to_filter_args('user', 'email:"test" or email:"example"')
        searches.to_filter_args('user', 'email:"test" OR email:"example"')

    def test_or(self):
        searches.to_filter_args('user', 'email:"test" and email:"example"')
        searches.to_filter_args('user', 'email:"test" AND email:"example"')

    def test_parenthesized(self):
        searches.to_filter_args('user', 'email:"word" or (email:"test" and email:"example")')
        searches.to_filter_args('user', 'email:"test" or (email:"example")')
        searches.to_filter_args('user', '(email:"test")')
        searches.to_filter_args('user', '((email:"test"))')

    def test_exclude(self):
        searches.to_filter_args('feed', 'uuid:!"99d63124-59e2-4204-ba61-be294dcb4d22|c54a1f76-f350-4336-b7c4-33ec8f5e81a3"')
