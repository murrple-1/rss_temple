from typing import Sequence

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as UserAdmin_
from django.db.models import QuerySet
from django.http.request import HttpRequest

from api.duplicate_feed_util import (
    DuplicateFeedTuple,
    convert_duplicate_feeds_to_alternate_feed_urls,
)
from api.models import (
    AlternateFeedURL,
    DuplicateFeedSuggestion,
    Feed,
    FeedEntry,
    SubscribedFeedUserMapping,
    User,
    UserCategory,
)


class SubscribedFeedsInline(admin.TabularInline):
    model = SubscribedFeedUserMapping
    extra = 0
    autocomplete_fields = ["feed", "user"]
    readonly_fields = ["custom_feed_title"]


@admin.register(User)
class UserAdmin(UserAdmin_):
    list_display = [
        "email",
        "created_at",
        "is_staff",
        "is_active",
        "subscribed_feeds__count",
    ]
    list_editable = ["is_staff", "is_active"]
    list_filter = ["is_active", "is_staff"]
    search_fields = ["email"]
    exclude = ["read_feed_entries", "favorite_feed_entries"]
    inlines = [SubscribedFeedsInline]
    ordering = ["email"]
    fieldsets = (
        (None, {"fields": ("email", "password", "last_login")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )

    @admin.display(description="Number of subscriptions")
    def subscribed_feeds__count(self, obj: User):  # pragma: no cover
        return obj.subscribed_feeds.count()


@admin.register(UserCategory)
class UserCategoryAdmin(admin.ModelAdmin):
    list_display = ["text", "user", "feeds__count"]
    list_select_related = ["user"]
    search_fields = ["text", "user__email"]
    autocomplete_fields = ["feeds"]

    @admin.display(description="Number of feeds")
    def feeds__count(self, obj: UserCategory):  # pragma: no cover
        return obj.feeds.count()


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = [
        "feed_url",
        "title",
        "home_url",
        "published_at",
        "subscribed_user_set__count",
        "feed_entries__count",
    ]
    search_fields = ["title", "feed_url", "home_url"]
    readonly_fields = ["home_url", "subscribed_user_set__count", "feed_entries__count"]

    def get_fields(
        self, request: HttpRequest, obj: Feed | None = None
    ) -> Sequence[str | Sequence[str]]:  # pragma: no cover
        fields = super().get_fields(request, obj)
        assert isinstance(fields, list)
        assert fields[2] == "title"
        assert fields[10] == "home_url"
        fields.insert(3, fields.pop(10))
        return fields

    @admin.display(description="Number of subscribed users")
    def subscribed_user_set__count(self, obj: Feed):  # pragma: no cover
        return obj.subscribed_user_set.count()

    @admin.display(description="Number of entries")
    def feed_entries__count(self, obj: Feed):  # pragma: no cover
        return obj.feed_entries.count()


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
    readonly_fields = ["id", "author_name"]

    @admin.display(description="Parent Feed URL")
    def feed__feed_url(self, obj: FeedEntry):  # pragma: no cover
        return obj.feed.feed_url

    @admin.display(description="Parent Feed Title")
    def feed__title(self, obj: FeedEntry):  # pragma: no cover
        return obj.feed.title

    def get_fields(
        self, request: HttpRequest, obj: FeedEntry | None = None
    ) -> Sequence[str | Sequence[str]]:  # pragma: no cover
        fields = super().get_fields(request, obj)
        assert isinstance(fields, list)
        assert fields[0] == "uuid"
        assert fields[15] == "id"
        fields.insert(1, fields.pop(15))
        assert fields[8] == "content"
        assert fields[16] == "author_name"
        fields.insert(9, fields.pop(16))
        return fields


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
        DuplicateFeedTuple(dfs.feed2, dfs.feed1) for dfs in queryset
    )


@admin.action(description="Convert to Alternate Feed URL (Feed 2 is the duplicate)")
def convert_duplicate_feed2_to_alternate_feed_url(
    modeladmin: "DuplicateFeedSuggestionAdmin",
    request: HttpRequest,
    queryset: QuerySet[DuplicateFeedSuggestion],
):  # pragma: no cover
    convert_duplicate_feeds_to_alternate_feed_urls(
        DuplicateFeedTuple(dfs.feed1, dfs.feed2) for dfs in queryset
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
