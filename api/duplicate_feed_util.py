import uuid
from typing import Callable, Collection

from django.db import IntegrityError, transaction

from api.models import (
    AlternateFeedURL,
    DuplicateFeedSuggestion,
    Feed,
    SubscribedFeedUserMapping,
    UserCategory,
)


def convert_duplicate_feeds_to_alternate_feed_urls(
    duplicate_feed_suggestions: Collection[DuplicateFeedSuggestion],
    master_feed_fn: Callable[[DuplicateFeedSuggestion], Feed],
    duplicate_feed_fn: Callable[[DuplicateFeedSuggestion], Feed],
) -> None:
    alternate_feed_urls: list[AlternateFeedURL] = []
    remove_feed_uuids: set[uuid.UUID] = set()
    moving_subscriptions: list[SubscribedFeedUserMapping] = []
    user_category_additions: dict[uuid.UUID, tuple[UserCategory, list[Feed]]] = {}
    for dfs in duplicate_feed_suggestions:
        master_feed = master_feed_fn(dfs)
        duplicate_feed = duplicate_feed_fn(dfs)

        for subsciption_mapping in SubscribedFeedUserMapping.objects.filter(
            feed=duplicate_feed
        ).iterator():
            subsciption_mapping.feed = master_feed
            moving_subscriptions.append(subsciption_mapping)

        for user_category in duplicate_feed.user_categories.iterator():
            tuple_: tuple[
                UserCategory, list[Feed]
            ] | None = user_category_additions.get(user_category.uuid)
            if not tuple_:
                tuple_ = (user_category, [])
                user_category_additions[user_category.uuid] = tuple_
            tuple_[1].append(master_feed)

        alternate_feed_urls.append(
            AlternateFeedURL(feed_url=duplicate_feed.feed_url, feed=master_feed)
        )
        remove_feed_uuids.add(duplicate_feed.uuid)

    with transaction.atomic():
        for user_category, feeds in user_category_additions.values():
            user_category.feeds.add(*feeds)

        for subsciption_mapping in moving_subscriptions:
            try:
                subsciption_mapping.save(update_fields=("feed",))
            except IntegrityError:
                # user was subscribed to both versions, for some reason
                pass

        AlternateFeedURL.objects.bulk_create(alternate_feed_urls)
        Feed.objects.filter(uuid__in=remove_feed_uuids).delete()
        # `DuplicateFeedSuggestion` are deleted via CASCADE
