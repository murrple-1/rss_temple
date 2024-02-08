import uuid
from typing import Any, Iterable, NamedTuple

from django.db import IntegrityError, transaction

from api.models import (
    AlternateFeedURL,
    Feed,
    FeedEntry,
    ReadFeedEntryUserMapping,
    SubscribedFeedUserMapping,
    User,
    UserCategory,
)


class DuplicateFeedTuple(NamedTuple):
    original_feed: Feed
    duplicate_feed: Feed


def convert_duplicate_feeds_to_alternate_feed_urls(
    duplicate_feed_suggestions: Iterable[DuplicateFeedTuple],
) -> None:
    alternate_feed_urls: list[AlternateFeedURL] = []
    remove_feed_uuids: set[uuid.UUID] = set()
    moving_subscriptions: list[SubscribedFeedUserMapping] = []
    moving_read_mappings: list[ReadFeedEntryUserMapping] = []
    moving_favorite_mappings: list[Any] = []
    user_category_additions: dict[uuid.UUID, tuple[UserCategory, list[Feed]]] = {}
    for original_feed, duplicate_feed in duplicate_feed_suggestions:
        for subsciption_mapping in SubscribedFeedUserMapping.objects.filter(
            feed=duplicate_feed
        ).iterator():
            subsciption_mapping.feed = original_feed
            moving_subscriptions.append(subsciption_mapping)

        for read_mapping in (
            ReadFeedEntryUserMapping.objects.filter(feed_entry__feed=duplicate_feed)
            .select_related("feed_entry")
            .iterator()
        ):
            similar_feed_entry = FeedEntry.objects.filter(
                feed=original_feed,
                title=read_mapping.feed_entry.title,
                url=read_mapping.feed_entry.url,
                is_archived=False,
            ).first()
            if similar_feed_entry:
                read_mapping.feed_entry = similar_feed_entry
                moving_read_mappings.append(read_mapping)

        for favorite_mapping in (
            User.favorite_feed_entries.through.objects.filter(
                feedentry__feed=duplicate_feed
            )
            .select_related("feedentry")
            .iterator()
        ):
            similar_feed_entry = FeedEntry.objects.filter(
                feed=original_feed,
                title=favorite_mapping.feedentry.title,
                url=favorite_mapping.feedentry.url,
                is_archived=False,
            ).first()
            if similar_feed_entry:
                favorite_mapping.feedentry = similar_feed_entry
                moving_favorite_mappings.append(favorite_mapping)

        for user_category in duplicate_feed.user_categories.iterator():
            user_category_feeds_tuple: tuple[
                UserCategory, list[Feed]
            ] | None = user_category_additions.get(user_category.uuid)
            if not user_category_feeds_tuple:
                user_category_feeds_tuple = (user_category, [])
                user_category_additions[user_category.uuid] = user_category_feeds_tuple
            user_category_feeds_tuple[1].append(original_feed)

        alternate_feed_urls.append(
            AlternateFeedURL(feed_url=duplicate_feed.feed_url, feed=original_feed)
        )
        remove_feed_uuids.add(duplicate_feed.uuid)

    with transaction.atomic():
        for subsciption_mapping in moving_subscriptions:
            try:
                with transaction.atomic():
                    subsciption_mapping.save(update_fields=("feed",))
            except IntegrityError:
                # user was subscribed to both versions, for some reason
                pass

        for moving_read_mapping in moving_read_mappings:
            try:
                with transaction.atomic():
                    moving_read_mapping.save(update_fields=("feed_entry",))
            except IntegrityError:
                # user was subscribed to both versions, for some reason
                pass

        for favorite_mapping in moving_favorite_mappings:
            try:
                with transaction.atomic():
                    favorite_mapping.save(update_fields=("feedentry",))
            except IntegrityError:
                # user was subscribed to both versions, for some reason
                pass

        for user_category, feeds in user_category_additions.values():
            user_category.feeds.add(*feeds)

        AlternateFeedURL.objects.bulk_create(alternate_feed_urls)
        Feed.objects.filter(uuid__in=remove_feed_uuids).delete()
        # `DuplicateFeedSuggestion` are deleted via CASCADE
