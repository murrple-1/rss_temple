from unittest import TestCase

from api import searches

class SearchesTestCase(TestCase):
    # TODO more tests
    def test_standard(self):
        searches.to_filter_args('feed', 'uuid:"99d63124-59e2-4204-ba61-be294dcb4d22|c54a1f76-f350-4336-b7c4-33ec8f5e81a3"')
