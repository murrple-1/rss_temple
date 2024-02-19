import logging
import uuid
from typing import Any, Callable, ClassVar, TypedDict
from unittest.mock import Mock

from django.db.models import Q, QuerySet
from django.db.models.manager import BaseManager
from django.http import HttpRequest
from django.test import SimpleTestCase, TestCase

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
        q_list = searches.to_filter_args(
            "feed",
            Mock(HttpRequest),
            'uuid:"99d63124-59e2-4204-ba61-be294dcb4d22,c54a1f76-f350-4336-b7c4-33ec8f5e81a3"',
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
        q_list = searches.to_filter_args(
            "feed", Mock(HttpRequest), 'title:"\\"test\\""'
        )
        try:
            self.assertEqual(q_list, [Q(title_search_vector='"test"')])
        except AssertionError:
            self.assertEqual(q_list, [Q(title__icontains='"test"')])

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
                "isSubscribed": ["true", "false"],
                "customTitle": ["custom title"],
                "customTitle_exact": ["custom title"],
                "customTitle_null": ["true", "false"],
                "calculatedTitle": ["calculated title"],
                "calculatedTitle_exact": ["calculated title"],
            },
        },
        "feedentry": {
            "get_queryset": lambda: FeedEntry.annotate_search_vectors(
                FeedEntry.annotate_user_data(
                    FeedEntry.objects.all(), AllSearchesTestCase.user
                )
            ),
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
                "isFromSubscription": ["true", "false"],
                "isRead": ["true", "false"],
                "isFavorite": ["true", "false"],
                "readAt": ["2018-11-23 00:00:00+0000|2018-11-26 00:00:00+0000"],
                "readAt_exact": ["2018-11-26 00:00:00+0000"],
                "readAt_delta": ["older_than:10h"],
                "isArchived": ["true", "false"],
                "languageIso639_3": ["ENG", "eng", "eng,deu"],
                "languageIso639_1": ["EN", "en", "en,de"],
                "languageName": ["ENGLISH", "english", "english,german"],
                "hasTopImageBeenProcessed": ["true", "false"],
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


class LanguageIso639_3SetTestCase(SimpleTestCase):
    def test_convertto(self):
        for input_, expected in [
            ("eng", ["ENG"]),
            ("eng,eng", ["ENG"]),
            ("eng,DEU", ["ENG", "DEU"]),
            ("und", ["UND"]),
            ("und,eng", ["UND", "ENG"]),
        ]:
            with self.subTest(input=input_, expected=expected):
                self.assertEqual(
                    searches.LanguageIso639_3Set.convertto(input_), frozenset(expected)
                )

    def test_convertto_bad(self):
        for input_ in ["", "abc", "ABC", "badlang", "eng,abc"]:
            with self.subTest(input=input_):
                with self.assertRaises(ValueError):
                    searches.LanguageIso639_3Set.convertto(input_)


class LanguageIso639_1SetTestCase(SimpleTestCase):
    def test_convertto(self):
        for input_, expected in [
            ("en", ["EN"]),
            ("en,en", ["EN"]),
            ("en,DE", ["EN", "DE"]),
            ("un", ["UN"]),
            ("un,en", ["UN", "EN"]),
        ]:
            with self.subTest(input=input_, expected=expected):
                self.assertEqual(
                    searches.LanguageIso639_1Set.convertto(input_), frozenset(expected)
                )

    def test_convertto_bad(self):
        for input_ in ["", "xx", "XX", "badlang", "en,xx"]:
            with self.subTest(input=input_):
                with self.assertRaises(ValueError):
                    searches.LanguageIso639_1Set.convertto(input_)


class LanguageNameSetTestCase(SimpleTestCase):
    def test_convertto(self):
        for input_, expected in [
            ("english", ["ENGLISH"]),
            ("english,english", ["ENGLISH"]),
            ("english,GERMAN", ["ENGLISH", "GERMAN"]),
            ("undefined", ["UNDEFINED"]),
            ("undefined,english", ["UNDEFINED", "ENGLISH"]),
        ]:
            with self.subTest(input=input_, expected=expected):
                self.assertEqual(
                    searches.LanguageNameSet.convertto(input_), frozenset(expected)
                )

    def test_convertto_bad(self):
        for input_ in ["", "xx", "XX", "badlang", "en,xx"]:
            with self.subTest(input=input_):
                with self.assertRaises(ValueError):
                    searches.LanguageNameSet.convertto(input_)


class URLTestCase(SimpleTestCase):
    def test_convertto(self):
        for input_, expected in [
            ("https://GOOGLE.COM", "https://google.com/"),
        ]:
            with self.subTest(input=input_, expected=expected):
                self.assertEqual(searches.URL.convertto(input_), expected)

    def test_convertto_bad(self):
        for input_ in ["//[oops"]:
            with self.subTest(input=input_):
                with self.assertRaises(ValueError):
                    searches.URL.convertto(input_)
