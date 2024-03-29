from typing import Callable, ClassVar, TypedDict

from django.db.models import F, QuerySet
from django.db.models.manager import BaseManager
from django.test import TestCase

from api import sorts
from api.models import Feed, FeedEntry, User, UserCategory


class SortsTestCase(TestCase):
    @staticmethod
    def _to_order_by_args(object_name, sort, default_sort_enabled):
        sort_list = sorts.to_sort_list(object_name, sort, default_sort_enabled)
        order_by_args = sorts.sort_list_to_order_by_args(object_name, sort_list)

        return order_by_args

    def test_default(self):
        order_by_args = SortsTestCase._to_order_by_args("feed", "title:ASC", True)

        self.assertEqual(order_by_args, [F("title").asc(), F("uuid").asc()])

    def test_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args("feed", "title:ASC", False)

        self.assertEqual(order_by_args, [F("title").asc()])

    def test_multiple_default(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "feed", "title:ASC,homeUrl:ASC", True
        )

        self.assertEqual(
            order_by_args, [F("title").asc(), F("home_url").asc(), F("uuid").asc()]
        )

    def test_multiple_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "feed", "title:ASC,homeUrl:ASC", False
        )

        self.assertEqual(order_by_args, [F("title").asc(), F("home_url").asc()])

    def test_descending_default(self):
        order_by_args = SortsTestCase._to_order_by_args("feed", "title:DESC", True)

        self.assertEqual(order_by_args, [F("title").desc(), F("uuid").asc()])

    def test_descending_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args("feed", "title:DESC", False)

        self.assertEqual(order_by_args, [F("title").desc()])

    def test_multiple_descending_default(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "feed", "title:DESC,homeUrl:DESC", True
        )

        self.assertEqual(
            order_by_args, [F("title").desc(), F("home_url").desc(), F("uuid").asc()]
        )

    def test_multiple_descending_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "feed", "title:DESC,homeUrl:DESC", False
        )

        self.assertEqual(order_by_args, [F("title").desc(), F("home_url").desc()])

    def test_multiple_mixed_default(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "feed", "title:DESC,homeUrl:ASC", True
        )

        self.assertEqual(
            order_by_args, [F("title").desc(), F("home_url").asc(), F("uuid").asc()]
        )

    def test_multiple_mixed_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "feed", "title:DESC,homeUrl:ASC", False
        )

        self.assertEqual(order_by_args, [F("title").desc(), F("home_url").asc()])

    def test_multiple_overwritedefault(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "feed", "uuid:ASC,title:DESC", True
        )

        self.assertEqual(order_by_args, [F("uuid").asc(), F("title").desc()])

    def test_sort_malformed(self):
        with self.assertRaises(ValueError):
            sorts.to_sort_list("feed", "bad sort string", True)

    def test_bad_sort_list(self):
        with self.assertRaises(AttributeError):
            sorts.sort_list_to_order_by_args(
                "feed",
                [
                    {
                        "field_name": "bad_field",
                        "direction": "ASC",
                    }
                ],
            )


class AllSortsTestCase(TestCase):
    user: ClassVar[User]

    class _Trial(TypedDict):
        get_queryset: Callable[[], BaseManager | QuerySet]

    TRIALS: dict[str, _Trial] = {
        "usercategory": {
            "get_queryset": lambda: UserCategory.objects,
        },
        "feed": {
            "get_queryset": lambda: Feed.annotate_search_vectors(
                Feed.annotate_subscription_data(
                    Feed.objects.all(), AllSortsTestCase.user
                )
            ),
        },
        "feedentry": {
            "get_queryset": lambda: FeedEntry.annotate_search_vectors(
                FeedEntry.annotate_user_data(
                    FeedEntry.objects.all(), AllSortsTestCase.user
                )
            ),
        },
    }

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test_searches@test.com", None)

    def test_run(self):
        self.assertEqual(len(AllSortsTestCase.TRIALS), len(sorts._sort_configs))

        for key, trial_dict in AllSortsTestCase.TRIALS.items():
            with self.subTest(key=key):
                sorts_dict = sorts._sort_configs[key]

                sort_keys = sorts_dict.keys()

                sort_list = sorts.to_sort_list(
                    key, ",".join(f"{sort_key}:ASC" for sort_key in sort_keys), False
                )

                order_by_args = sorts.sort_list_to_order_by_args(key, sort_list)

                result = list(trial_dict["get_queryset"]().order_by(*order_by_args))

                self.assertIsNotNone(result)
