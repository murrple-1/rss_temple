from django.contrib import admin
from django.db.models import QuerySet
from django.http.request import HttpRequest

from api.duplicate_feed_util import convert_duplicate_feeds_to_alternate_feed_urls
from api.models import (
    AlternateFeedURL,
    DuplicateFeedSuggestion,
    Feed,
    FeedEntry,
    User,
    UserCategory,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    search_fields = ["email"]


@admin.register(UserCategory)
class UserCategoryAdmin(admin.ModelAdmin):
    search_fields = ["text"]


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = ["feed_url", "title", "home_url", "published_at"]
    search_fields = ["title", "feed_url", "home_url"]


@admin.register(FeedEntry)
class FeedEntryAdmin(admin.ModelAdmin):
    list_display = ["url", "title", "feed", "published_at", "is_archived"]
    list_filter = ["is_archived"]
    search_fields = ["feed__feed_url"]


@admin.register(AlternateFeedURL)
class AlternateFeedURLAdmin(admin.ModelAdmin):
    list_display = ["feed_url", "feed"]
    search_fields = ["feed_url"]


@admin.action(description="Convert to Alternate Feed URL (Feed 1 is the duplicate)")
def convert_duplicate_feed1_to_alternate_feed_url(
    modeladmin: "DuplicateFeedSuggestionAdmin",
    request: HttpRequest,
    queryset: QuerySet[DuplicateFeedSuggestion],
):
    convert_duplicate_feeds_to_alternate_feed_urls(
        queryset, lambda dfs: dfs.feed2, lambda dfs: dfs.feed1
    )


@admin.action(description="Convert to Alternate Feed URL (Feed 2 is the duplicate)")
def convert_duplicate_feed2_to_alternate_feed_url(
    modeladmin: "DuplicateFeedSuggestionAdmin",
    request: HttpRequest,
    queryset: QuerySet[DuplicateFeedSuggestion],
):
    convert_duplicate_feeds_to_alternate_feed_urls(
        queryset, lambda dfs: dfs.feed1, lambda dfs: dfs.feed2
    )


@admin.register(DuplicateFeedSuggestion)
class DuplicateFeedSuggestionAdmin(admin.ModelAdmin):
    actions = [
        convert_duplicate_feed1_to_alternate_feed_url,
        convert_duplicate_feed2_to_alternate_feed_url,
    ]
    list_display = ["uuid", "feed1", "feed2", "is_ignored"]
    list_editable = ["is_ignored"]
    list_filter = ["is_ignored"]
    search_fields = ["feed1__feed_url", "feed2__feed_url"]
