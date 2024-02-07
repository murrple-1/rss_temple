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
    list_display = ["email", "created_at", "is_staff", "is_active"]
    list_editable = ["is_staff", "is_active"]
    list_filter = ["is_active", "is_staff"]
    search_fields = ["email"]
    exclude = ["read_feed_entries", "favorite_feed_entries"]


@admin.register(UserCategory)
class UserCategoryAdmin(admin.ModelAdmin):
    list_display = ["text", "user__email"]
    list_select_related = ["user"]
    search_fields = ["text", "user__email"]
    autocomplete_fields = ["feeds"]

    @admin.display(description="Username")
    def user__email(self, obj: UserCategory):  # pragma: no cover
        return obj.user.email


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = ["feed_url", "title", "home_url", "published_at"]
    search_fields = ["title", "feed_url", "home_url"]


@admin.register(FeedEntry)
class FeedEntryAdmin(admin.ModelAdmin):
    list_display = [
        "url",
        "title",
        "feed__feed_url",
        "feed__title",
        "published_at",
        "is_archived",
    ]
    list_filter = ["is_archived"]
    list_editable = ["is_archived"]
    list_select_related = ["feed"]
    autocomplete_fields = ["feed"]
    search_fields = ["feed__feed_url"]

    @admin.display(description="Parent Feed URL")
    def feed__feed_url(self, obj: FeedEntry):  # pragma: no cover
        return obj.feed.feed_url

    @admin.display(description="Parent Feed Title")
    def feed__title(self, obj: FeedEntry):  # pragma: no cover
        return obj.feed.title


@admin.register(AlternateFeedURL)
class AlternateFeedURLAdmin(admin.ModelAdmin):
    list_display = ["feed_url", "feed__feed_url", "feed__title"]
    list_select_related = ["feed"]
    search_fields = ["feed_url", "feed__feed_url"]
    autocomplete_fields = ["feed"]

    @admin.display(description="Parent Feed URL")
    def feed__feed_url(self, obj: AlternateFeedURL):  # pragma: no cover
        return obj.feed.feed_url

    @admin.display(description="Parent Feed Title")
    def feed__title(self, obj: AlternateFeedURL):  # pragma: no cover
        return obj.feed.title


@admin.action(description="Convert to Alternate Feed URL (Feed 1 is the duplicate)")
def convert_duplicate_feed1_to_alternate_feed_url(
    modeladmin: "DuplicateFeedSuggestionAdmin",
    request: HttpRequest,
    queryset: QuerySet[DuplicateFeedSuggestion],
):  # pragma: no cover
    convert_duplicate_feeds_to_alternate_feed_urls(
        queryset, lambda dfs: dfs.feed2, lambda dfs: dfs.feed1
    )


@admin.action(description="Convert to Alternate Feed URL (Feed 2 is the duplicate)")
def convert_duplicate_feed2_to_alternate_feed_url(
    modeladmin: "DuplicateFeedSuggestionAdmin",
    request: HttpRequest,
    queryset: QuerySet[DuplicateFeedSuggestion],
):  # pragma: no cover
    convert_duplicate_feeds_to_alternate_feed_urls(
        queryset, lambda dfs: dfs.feed1, lambda dfs: dfs.feed2
    )


@admin.register(DuplicateFeedSuggestion)
class DuplicateFeedSuggestionAdmin(admin.ModelAdmin):
    actions = [
        convert_duplicate_feed1_to_alternate_feed_url,
        convert_duplicate_feed2_to_alternate_feed_url,
    ]
    list_display = [
        "uuid",
        "feed1__feed_url",
        "feed1__title",
        "feed2__feed_url",
        "feed2__title",
        "is_ignored",
    ]
    list_editable = ["is_ignored"]
    list_filter = ["is_ignored"]
    list_select_related = ["feed1", "feed2"]
    autocomplete_fields = ["feed1", "feed2"]
    search_fields = ["feed1__feed_url", "feed2__feed_url"]

    @admin.display(description="Feed 1 Feed URL")
    def feed1__feed_url(self, obj: DuplicateFeedSuggestion):  # pragma: no cover
        return obj.feed1.feed_url

    @admin.display(description="Feed 1 Title")
    def feed1__title(self, obj: DuplicateFeedSuggestion):  # pragma: no cover
        return obj.feed1.title

    @admin.display(description="Feed 2 Feed URL")
    def feed2__feed_url(self, obj: DuplicateFeedSuggestion):  # pragma: no cover
        return obj.feed2.feed_url

    @admin.display(description="Feed 2 Title")
    def feed2__title(self, obj: DuplicateFeedSuggestion):  # pragma: no cover
        return obj.feed2.title
