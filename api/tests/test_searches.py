import logging
import uuid
from typing import Any, Callable, ClassVar, TypedDict
from unittest.mock import Mock

from django.db.models import QuerySet
from django.db.models.manager import BaseManager
from django.http import HttpRequest
from django.test import TestCase

from api import searches
from api.models import Feed, FeedEntry, User, UserCategory


class SearchesTestCase(TestCase):
    old_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_logger_level)

    def test_standard(self):
        searches.to_filter_args(
            "feed",
            Mock(HttpRequest),
            'uuid:"99d63124-59e2-4204-ba61-be294dcb4d22,c54a1f76-f350-4336-b7c4-33ec8f5e81a3"',
        )

    def test_malformed(self):
        with self.assertRaises(ValueError):
            searches.to_filter_args("feed", Mock(HttpRequest), "")

        with self.assertRaises(ValueError):
            searches.to_filter_args("feed", Mock(HttpRequest), '((title:"test")')

    def test_unknown_field(self):
        with self.assertRaises(AttributeError):
            searches.to_filter_args("feed", Mock(HttpRequest), 'unknownfield:"test"')

    def test_malformed_value(self):
        with self.assertRaises(ValueError):
            searches.to_filter_args("feed", Mock(HttpRequest), 'uuid:"bad uuid"')

    def test_and(self):
        searches.to_filter_args(
            "feed", Mock(HttpRequest), 'title:"test" or title:"example"'
        )
        searches.to_filter_args(
            "feed", Mock(HttpRequest), 'title:"test" OR title:"example"'
        )

    def test_or(self):
        searches.to_filter_args(
            "feed", Mock(HttpRequest), 'title:"test" and title:"example"'
        )
        searches.to_filter_args(
            "feed", Mock(HttpRequest), 'title:"test" AND title:"example"'
        )

    def test_parenthesized(self):
        searches.to_filter_args(
            "feed",
            Mock(HttpRequest),
            'title:"word" or (title:"test" and title:"example")',
        )
        searches.to_filter_args(
            "feed", Mock(HttpRequest), 'title:"test" or (title:"example")'
        )
        searches.to_filter_args("feed", Mock(HttpRequest), '(title:"test")')
        searches.to_filter_args("feed", Mock(HttpRequest), '((title:"test"))')

    def test_exclude(self):
        searches.to_filter_args(
            "feed",
            Mock(HttpRequest),
            'uuid:!"99d63124-59e2-4204-ba61-be294dcb4d22,c54a1f76-f350-4336-b7c4-33ec8f5e81a3"',
        )


class AllSearchesTestCase(TestCase):
    old_logger_level: ClassVar[int]
    user: ClassVar[User]

    class _Trial(TypedDict):
        get_queryset: Callable[[], BaseManager | QuerySet[Any]]
        searches: dict[str, list[Any]]

    TRIALS: dict[str, _Trial] = {
        "usercategory": {
            "get_queryset": lambda: UserCategory.objects,
            "searches": {
                "uuid": [str(uuid.uuid4())],
                "text": ["test"],
                "text_exact": ["test"],
            },
        },
        "feed": {
            "get_queryset": lambda: Feed.annotate_search_vectors(
                Feed.annotate_subscription_data(
                    Feed.objects.all(), AllSearchesTestCase.user
                )
            ),
            "searches": {
                "uuid": [str(uuid.uuid4())],
                "title": ["test"],
                "title_exact": ["test"],
                "feedUrl": ["http://example.com/rss.xml"],
                "homeUrl": ["http://example.com"],
                "publishedAt": ["2018-11-23 00:00:00+0000|2018-11-26 00:00:00+0000"],
                "publishedAt_exact": ["2018-11-26 00:00:00+0000"],
                "publishedAt_delta": ["older_than:10h"],
                "updatedAt": ["2018-11-23 00:00:00+0000|2018-11-26 00:00:00+0000"],
                "updatedAt_exact": ["2018-11-26 00:00:00+0000"],
                "updatedAt_delta": ["older_than:10h"],
                "subscribed": ["true", "false"],
                "customTitle": ["custom title"],
                "customTitle_exact": ["custom title"],
                "customTitle_null": ["true", "false"],
                "calculatedTitle": ["calculated title"],
                "calculatedTitle_exact": ["calculated title"],
            },
        },
        "feedentry": {
            "get_queryset": lambda: FeedEntry.objects,
            "searches": {
                "uuid": [str(uuid.uuid4())],
                "feedUuid": [str(uuid.uuid4())],
                "feedUrl": ["http://example.com/rss.xml"],
                "createdAt": ["2018-11-23 00:00:00+0000|2018-11-26 00:00:00+0000"],
                "createdAt_exact": ["2018-11-26 00:00:00+0000"],
                "createdAt_delta": ["older_than:10h"],
                "publishedAt": ["2018-11-23 00:00:00+0000|2018-11-26 00:00:00+0000"],
                "publishedAt_exact": ["2018-11-26 00:00:00+0000"],
                "publishedAt_delta": ["older_than:10h"],
                "updatedAt": ["2018-11-23 00:00:00+0000|2018-11-26 00:00:00+0000"],
                "updatedAt_exact": ["2018-11-26 00:00:00+0000"],
                "updatedAt_delta": ["older_than:10h"],
                "url": ["http://example.com/entry1.html"],
                "authorName": ["John Doe"],
                "authorName_exact": ["John Doe"],
                "title": ["Some Text"],
                "content": ["Some Text"],
                "subscribed": ["true", "false"],
                "isRead": ["true", "false"],
                "isFavorite": ["true", "false"],
                "readAt": ["2018-11-23 00:00:00+0000|2018-11-26 00:00:00+0000"],
                "readAt_exact": ["2018-11-26 00:00:00+0000"],
                "readAt_delta": ["older_than:10h"],
                "isArchived": ["true", "false"],
            },
        },
    }

    class MockRequest(Mock):
        def __init__(self):
            super().__init__(HttpRequest)
            self.user = AllSearchesTestCase.user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_logger_level)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test_searches@test.com", None)

    def test_run(self):
        self.assertEqual(len(AllSearchesTestCase.TRIALS), len(searches._search_fns))

        for key, trial_dict in AllSearchesTestCase.TRIALS.items():
            with self.subTest(key=key):
                search_fns_dict = searches._search_fns[key]

                trial_searches = trial_dict["searches"]
                self.assertEqual(len(trial_searches), len(search_fns_dict))

                queryset = trial_dict["get_queryset"]()

                for field, test_values in trial_searches.items():
                    for test_value in test_values:
                        with self.subTest(field=field, test_value=test_value):
                            q = search_fns_dict[field](
                                AllSearchesTestCase.MockRequest(),
                                test_value,
                            )
                            result = list(queryset.filter(q))

                            self.assertIsNotNone(result)
