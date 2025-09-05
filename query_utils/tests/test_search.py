import logging
import uuid
from typing import Callable, ClassVar
from unittest.mock import Mock

from django.db.models import Q
from django.http import HttpRequest
from django.test import SimpleTestCase

from query_utils import search as searchutils
from query_utils.search.convertto import UuidList

search_fns: dict[str, dict[str, Callable[[HttpRequest, str], Q]]] = {
    "object": {
        "uuid": lambda request, search_obj: Q(uuid__in=UuidList.convertto(search_obj)),
        "text": lambda request, search_obj: Q(text__icontains=search_obj),
    },
}


class SearchesTestCase(SimpleTestCase):
    old_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_logger_level = logging.getLogger(
            "rss_temple.query_utils"
        ).getEffectiveLevel()

        logging.getLogger("rss_temple.query_utils").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple.query_utils").setLevel(cls.old_logger_level)

    def test_standard(self):
        q_list = searchutils.to_filter_args(
            "object",
            Mock(HttpRequest),
            'uuid:"99d63124-59e2-4204-ba61-be294dcb4d22,c54a1f76-f350-4336-b7c4-33ec8f5e81a3"',
            search_fns,
        )

        try:
            self.assertEqual(
                q_list,
                [
                    Q(
                        uuid__in=[
                            uuid.UUID("c54a1f76-f350-4336-b7c4-33ec8f5e81a3"),
                            uuid.UUID("99d63124-59e2-4204-ba61-be294dcb4d22"),
                        ]
                    )
                ],
            )
        except AssertionError:
            self.assertEqual(
                q_list,
                [
                    Q(
                        uuid__in=[
                            uuid.UUID("99d63124-59e2-4204-ba61-be294dcb4d22"),
                            uuid.UUID("c54a1f76-f350-4336-b7c4-33ec8f5e81a3"),
                        ]
                    )
                ],
            )

    def test_standard_with_inner_quote(self):
        q_list = searchutils.to_filter_args(
            "object",
            Mock(HttpRequest),
            'text:"\\"test\\""',
            search_fns,
        )
        self.assertEqual(q_list, [Q(text__icontains='"test"')])

    def test_malformed(self):
        with self.assertRaises(ValueError):
            searchutils.to_filter_args(
                "object",
                Mock(HttpRequest),
                "",
                search_fns,
            )

        with self.assertRaises(ValueError):
            searchutils.to_filter_args(
                "object", Mock(HttpRequest), '((text:"test")', search_fns
            )

    def test_unknown_field(self):
        with self.assertRaises(AttributeError):
            searchutils.to_filter_args(
                "object", Mock(HttpRequest), 'unknownfield:"test"', search_fns
            )

    def test_malformed_value(self):
        with self.assertRaises(ValueError):
            searchutils.to_filter_args(
                "object", Mock(HttpRequest), 'uuid:"bad uuid"', search_fns
            )

    def test_and(self):
        searchutils.to_filter_args(
            "object", Mock(HttpRequest), 'text:"test" or text:"example"', search_fns
        )
        searchutils.to_filter_args(
            "object", Mock(HttpRequest), 'text:"test" OR text:"example"', search_fns
        )

    def test_or(self):
        searchutils.to_filter_args(
            "object", Mock(HttpRequest), 'text:"test" and text:"example"', search_fns
        )
        searchutils.to_filter_args(
            "object", Mock(HttpRequest), 'text:"test" AND text:"example"', search_fns
        )

    def test_parenthesized(self):
        searchutils.to_filter_args(
            "object",
            Mock(HttpRequest),
            'text:"word" or (text:"test" and text:"example")',
            search_fns,
        )
        searchutils.to_filter_args(
            "object", Mock(HttpRequest), 'text:"test" or (text:"example")', search_fns
        )
        searchutils.to_filter_args(
            "object", Mock(HttpRequest), '(text:"test")', search_fns
        )
        searchutils.to_filter_args(
            "object", Mock(HttpRequest), '((text:"test"))', search_fns
        )

    def test_exclude(self):
        searchutils.to_filter_args(
            "object",
            Mock(HttpRequest),
            'uuid:!"99d63124-59e2-4204-ba61-be294dcb4d22,c54a1f76-f350-4336-b7c4-33ec8f5e81a3"',
            search_fns,
        )
