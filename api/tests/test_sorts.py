from typing import Callable, ClassVar, TypedDict

from django.db.models import F, QuerySet
from django.db.models.manager import BaseManager
from django.test import TestCase

from api import sorts
from api.models import Feed, FeedEntry, User, UserCategory
from query_utils import sort as sortutils


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
        self.assertEqual(len(AllSortsTestCase.TRIALS), len(sorts.sort_configs))

        for key, trial_dict in AllSortsTestCase.TRIALS.items():
            with self.subTest(key=key):
                sorts_dict = sorts.sort_configs[key]

                sort_keys = sorts_dict.keys()

                sort_list = sortutils.to_sort_list(
                    key,
                    ",".join(f"{sort_key}:ASC" for sort_key in sort_keys),
                    False,
                    sorts.sort_configs,
                )

                order_by_args = sortutils.sort_list_to_order_by_args(
                    key, sort_list, sorts.sort_configs
                )

                result = list(trial_dict["get_queryset"]().order_by(*order_by_args))

                self.assertIsNotNone(result)
