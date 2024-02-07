import uuid
from typing import Callable, Collection

from django.db import IntegrityError, transaction

from api.models import (
    AlternateFeedURL,
    DuplicateFeedSuggestion,
    Feed,
    FeedEntry,
    ReadFeedEntryUserMapping,
    SubscribedFeedUserMapping,
    User,
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
    moving_read_mappings: list[ReadFeedEntryUserMapping] = []
    favorite_additions: dict[uuid.UUID, tuple[User, list[FeedEntry]]] = {}
    user_category_additions: dict[uuid.UUID, tuple[UserCategory, list[Feed]]] = {}
    for dfs in duplicate_feed_suggestions:
        master_feed = master_feed_fn(dfs)
        duplicate_feed = duplicate_feed_fn(dfs)

        for subsciption_mapping in SubscribedFeedUserMapping.objects.filter(
            feed=duplicate_feed
        ).iterator():
            subsciption_mapping.feed = master_feed
            moving_subscriptions.append(subsciption_mapping)

        for read_mapping in (
            ReadFeedEntryUserMapping.objects.filter(feed_entry__feed=duplicate_feed)
            .select_related("feed_entry")
            .iterator()
        ):
            similar_feed_entry = FeedEntry.objects.filter(
                feed=master_feed,
                title=read_mapping.feed_entry.title,
                url=read_mapping.feed_entry.url,
                is_archived=False,
            ).first()
            if similar_feed_entry:
                read_mapping.feed_entry = similar_feed_entry
                moving_read_mappings.append(read_mapping)

        for feed_entry in FeedEntry.objects.filter(
            feed=duplicate_feed, is_archived=False
        ).iterator():
            similar_feed_entry = FeedEntry.objects.filter(
                feed=master_feed,
                title=feed_entry.title,
                url=feed_entry.url,
                is_archived=False,
            ).first()
            if similar_feed_entry:
                for user in feed_entry.favorite_user_set.iterator():
                    user_feed_entries_tuple: tuple[
                        User, list[FeedEntry]
                    ] | None = favorite_additions.get(user.uuid)
                    if not user_feed_entries_tuple:
                        user_feed_entries_tuple = (user, [])
                        favorite_additions[user.uuid] = user_feed_entries_tuple
                    user_feed_entries_tuple[1].append(similar_feed_entry)

        for user_category in duplicate_feed.user_categories.iterator():
            user_category_feeds_tuple: tuple[
                UserCategory, list[Feed]
            ] | None = user_category_additions.get(user_category.uuid)
            if not user_category_feeds_tuple:
                user_category_feeds_tuple = (user_category, [])
                user_category_additions[user_category.uuid] = user_category_feeds_tuple
            user_category_feeds_tuple[1].append(master_feed)

        alternate_feed_urls.append(
            AlternateFeedURL(feed_url=duplicate_feed.feed_url, feed=master_feed)
        )
        remove_feed_uuids.add(duplicate_feed.uuid)

    with transaction.atomic():
        for user, feed_entries in favorite_additions.values():
            user.favorite_feed_entries.add(*feed_entries)

        for user_category, feeds in user_category_additions.values():
            user_category.feeds.add(*feeds)

        for subsciption_mapping in moving_subscriptions:
            try:
                subsciption_mapping.save(update_fields=("feed",))
            except IntegrityError:
                # user was subscribed to both versions, for some reason
                pass

        for moving_read_mapping in moving_read_mappings:
            try:
                moving_read_mapping.save(update_fields=("feed_entry",))
            except IntegrityError:
                # user was subscribed to both versions, for some reason
                pass

        AlternateFeedURL.objects.bulk_create(alternate_feed_urls)
        Feed.objects.filter(uuid__in=remove_feed_uuids).delete()
        # `DuplicateFeedSuggestion` are deleted via CASCADE
