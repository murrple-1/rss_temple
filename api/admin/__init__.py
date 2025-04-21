from typing import Any, Sequence
import uuid

from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.auth.admin import UserAdmin as UserAdmin_
from django.db.models import QuerySet
from django.http import HttpResponse, HttpResponseRedirect
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
    FeedEntryReport,
    SubscribedFeedUserMapping,
    User,
    UserCategory,
    FeedReport,
    RemovedFeed,
)
from api.admin import remove_feeds_util


class SubscribedFeedsInline(admin.TabularInline):
    model = SubscribedFeedUserMapping
    autocomplete_fields = ["feed", "user"]
    readonly_fields = ["custom_feed_title"]

    def has_add_permission(
        self, request: HttpRequest, obj: Any | None
    ) -> bool:  # pragma: no cover
        return False


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
    search_fields = ["title", "url", "feed__feed_url", "feed__title"]
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


@admin.register(DuplicateFeedSuggestion)
class DuplicateFeedSuggestionAdmin(admin.ModelAdmin):
    actions = [
        "convert_duplicate_feed1_to_alternate_feed_url",
        "convert_duplicate_feed2_to_alternate_feed_url",
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

    @admin.action(description="Convert to Alternate Feed URL (Feed 1 is the duplicate)")
    def convert_duplicate_feed1_to_alternate_feed_url(
        self,
        request: HttpRequest,
        queryset: QuerySet[DuplicateFeedSuggestion],
    ):  # pragma: no cover
        convert_duplicate_feeds_to_alternate_feed_urls(
            DuplicateFeedTuple(dfs.feed2, dfs.feed1) for dfs in queryset
        )

    @admin.action(description="Convert to Alternate Feed URL (Feed 2 is the duplicate)")
    def convert_duplicate_feed2_to_alternate_feed_url(
        self,
        request: HttpRequest,
        queryset: QuerySet[DuplicateFeedSuggestion],
    ):  # pragma: no cover
        convert_duplicate_feeds_to_alternate_feed_urls(
            DuplicateFeedTuple(dfs.feed1, dfs.feed2) for dfs in queryset
        )

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


@admin.register(FeedReport)
class FeedReportAdmin(admin.ModelAdmin):
    actions = ["remove_feeds"]
    autocomplete_fields = ["feed"]
    list_filter = ["is_ignored"]
    list_display = [
        "uuid",
        "feed__feed_url",
        "feed__title",
        "is_ignored",
    ]
    list_editable = ["is_ignored"]
    search_fields = ["feed__feed_url", "feed__title"]

    @admin.action(description="Remove (ban) Feed(s)")
    def remove_feeds(
        self,
        request: HttpRequest,
        queryset: QuerySet[FeedReport],
    ):
        if "apply" in request.POST:
            return self._remove_feeds__action__end(request, queryset)
        else:
            return self._remove_feeds__action__begin(request, queryset)

    def _remove_feeds__action__begin(
        self, request: HttpRequest, queryset: QuerySet[FeedReport]
    ) -> HttpResponse:
        return remove_feeds_util.render(
            request,
            remove_feeds_util.generate_formset(
                Feed.objects.filter(uuid__in=queryset.values("feed_id"))
            ),
            [
                str(uuid_)
                for uuid_ in frozenset(queryset.values_list("uuid", flat=True))
            ],
        )

    def _remove_feeds__action__end(
        self, request: HttpRequest, queryset: QuerySet[FeedReport]
    ) -> HttpResponse:
        formset = remove_feeds_util.generate_formset(
            Feed.objects.filter(uuid__in=queryset.values("feed_id")), request.POST
        )
        if formset.is_valid():
            feed_id_to_reason_mapping: dict[uuid.UUID, str] = {
                uuid.UUID(form.cleaned_data["feed_id"]): form.cleaned_data["reason"]
                for form in formset
            }
            remove_feeds_util.remove_feeds(feed_id_to_reason_mapping)
            self.message_user(request, f"You validated {len(formset)} feed reports")
            return HttpResponseRedirect(request.get_full_path())
        else:
            return remove_feeds_util.render(
                request, formset, request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            )


@admin.register(FeedEntryReport)
class FeedEntryReportAdmin(admin.ModelAdmin):
    actions = ["remove_feeds"]
    autocomplete_fields = ["feed_entry"]
    list_filter = ["is_ignored"]
    list_display = [
        "uuid",
        "feed_entry__title",
        "feed_entry__feed__feed_url",
        "feed_entry__feed__title",
        "is_ignored",
    ]
    list_editable = ["is_ignored"]
    search_fields = [
        "title",
        "url",
        "feed_entry__feed__feed_url",
        "feed_entry__feed__title",
    ]

    @admin.action(description="Remove (ban) Feed(s)")
    def remove_feeds(
        self,
        request: HttpRequest,
        queryset: QuerySet[FeedEntryReport],
    ):
        if "apply" in request.POST:
            return self._remove_feeds__action__end(request, queryset)
        else:
            return self._remove_feeds__action__begin(request, queryset)

    def _remove_feeds__action__begin(
        self, request: HttpRequest, queryset: QuerySet[FeedEntryReport]
    ) -> HttpResponse:
        return remove_feeds_util.render(
            request,
            remove_feeds_util.generate_formset(
                Feed.objects.filter(uuid__in=queryset.values("feed_entry__feed_id"))
            ),
            [
                str(uuid_)
                for uuid_ in frozenset(queryset.values_list("uuid", flat=True))
            ],
        )

    def _remove_feeds__action__end(
        self, request: HttpRequest, queryset: QuerySet[FeedEntryReport]
    ) -> HttpResponse:
        formset = remove_feeds_util.generate_formset(
            Feed.objects.filter(uuid__in=queryset.values("feed_entry__feed_id")),
            request.POST,
        )
        if formset.is_valid():
            feed_id_to_reason_mapping: dict[uuid.UUID, str] = {
                uuid.UUID(form.cleaned_data["feed_id"]): form.cleaned_data["reason"]
                for form in formset
            }
            remove_feeds_util.remove_feeds(feed_id_to_reason_mapping)
            self.message_user(
                request, f"You validated {len(formset)} feed entry reports"
            )
            return HttpResponseRedirect(request.get_full_path())
        else:
            return remove_feeds_util.render(
                request, formset, request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            )


@admin.register(RemovedFeed)
class RemovedFeedAdmin(admin.ModelAdmin):
    pass
