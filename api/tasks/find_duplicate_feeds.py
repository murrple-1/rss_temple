import itertools
from typing import NamedTuple

from api.models import Feed


class DuplicateReasonsDescriptor(NamedTuple):
    entry_tuple_intersection: frozenset[tuple[str, str]]


def find_duplicate_feeds(
    feed_count: int,
    entry_compare_count: int,
    entry_intersection_threshold: int,
) -> list[tuple[Feed, Feed]]:
    return [
        (f1, f2)
        for f1, f2 in itertools.combinations(Feed.objects.order_by("?")[:feed_count], 2)
        if are_feeds_duplicate(
            f1,
            f2,
            entry_compare_count,
            entry_intersection_threshold,
        )
        is not None
    ]


def are_feeds_duplicate(
    f1: Feed,
    f2: Feed,
    entry_compare_count: int,
    entry_intersection_threshold: int,
) -> DuplicateReasonsDescriptor | None:
    if f1.title != f2.title:
        return None

    if f1.home_url != f2.home_url:
        return None

    f1_entry_tuples: frozenset[tuple[str, str]] | None = getattr(
        f1, "_entry_tuples", None
    )
    if f1_entry_tuples is None:
        f1_entry_tuples = frozenset(
            (fe.title, fe.url)
            for fe in f1.feed_entries.order_by("-published_at")[:entry_compare_count]
        )
        setattr(f1, "_entry_tuples", f1_entry_tuples)

    f2_entry_tuples: frozenset[tuple[str, str]] | None = getattr(
        f2, "_entry_tuples", None
    )
    if f2_entry_tuples is None:
        f2_entry_tuples = frozenset(
            (fe.title, fe.url)
            for fe in f2.feed_entries.order_by("-published_at")[:entry_compare_count]
        )
        setattr(f2, "_entry_tuples", f2_entry_tuples)

    entry_tuple_intersection = f1_entry_tuples.intersection(f2_entry_tuples)
    if len(entry_tuple_intersection) <= entry_intersection_threshold:
        return None

    return DuplicateReasonsDescriptor(entry_tuple_intersection)
