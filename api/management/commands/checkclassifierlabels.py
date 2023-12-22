import warnings
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand

from api.models import ClassifierLabel

_EXPECTED_LABELS = [
    "Anime & Manga",
    "Arts & Craft",
    "Automobile & Vehicles",
    "Books",
    "Business, Finance & Banking",
    "Celebrities & Culture",
    "Computer Hardware & Software",
    "Education",
    "Fashion & Beauty",
    "Food & Drink",
    "Gaming",
    "Health",
    "Movies & TV",
    "Music",
    "News & Weather",
    "Pets & Animals",
    "Photography",
    "Politics",
    "Programming",
    "Religion",
    "Science & Technology",
    "Sport",
    "Travel",
]


class Command(BaseCommand):
    help = "Check to make sure the classifier labels are correct, via comparison with a hardcoded list"

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        expected_labels = frozenset(_EXPECTED_LABELS)
        if len(expected_labels) < len(_EXPECTED_LABELS):
            warnings.warn(
                "_EXPECTED_LABELS contains duplicates: {}".format(
                    ", ".join(
                        f"'{t}'"
                        for t, count in Counter(_EXPECTED_LABELS).items()
                        if count > 1
                    )
                )
            )

        labels = frozenset(ClassifierLabel.objects.values_list("text", flat=True))

        if missing_expected_labels := expected_labels.difference(labels):
            warnings.warn(
                "missing labels: {}".format(
                    ", ".join(f"'{t}'" for t in missing_expected_labels)
                )
            )

        if extra_labels := labels.difference(expected_labels):
            warnings.warn(
                "extra labels: {}".format(", ".join(f"'{t}'" for t in extra_labels))
            )
