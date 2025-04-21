from collections import defaultdict
from typing import Any, Sequence
import uuid

from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.auth.admin import UserAdmin as UserAdmin_
from django.db.models import QuerySet
from django.forms import BaseFormSet
from django.http import HttpResponse, HttpResponseRedirect, QueryDict
from django.http.request import HttpRequest
from django.db import transaction
from django.shortcuts import render

from api.duplicate_feed_util import (
    DuplicateFeedTuple,
    convert_duplicate_feeds_to_alternate_feed_urls,
)
from api.forms import RemoveFeedsFormset
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


def _remove_feeds_render(
    request: HttpRequest, formset: BaseFormSet, selection_action_ids: list[str]
) -> HttpResponse:
    return render(
        request,
        "admin/remove_feeds.html",
        {
            "title": "Remove Feeds",
            "formset": formset,
            "selected_action_ids": selection_action_ids,
        },
    )


def _remove_feeds(
    request: HttpRequest, formset: BaseFormSet
) -> tuple[bool, HttpResponse]:
    if formset.is_valid():
        feed_uuids = [uuid.UUID(form.cleaned_data["feed_id"]) for form in formset]

        feeds = {f.uuid: f for f in Feed.objects.filter(uuid__in=feed_uuids)}

        alternate_feed_urls: dict[str, list[AlternateFeedURL]] = defaultdict(list)
        for afu in AlternateFeedURL.objects.filter(feed_id__in=feed_uuids):
            alternate_feed_urls[afu.feed.feed_url].append(afu)

        remove_urls_and_reasons: dict[str, tuple[str, str]] = {}
        for form in formset:
            feed = feeds[uuid.UUID(form.cleaned_data["feed_id"])]
            reason = form.cleaned_data["reason"]
            assert isinstance(reason, str)

            remove_urls_and_reasons[feed.feed_url] = (feed.feed_url, reason)

            for alternate_feed_url in alternate_feed_urls[feed.feed_url]:
                remove_urls_and_reasons[alternate_feed_url.feed_url] = (
                    alternate_feed_url.feed_url,
                    f"duplicate of {feed.feed_url}\n---\n{reason}",
                )

        with transaction.atomic():
            Feed.objects.filter(feed_url__in=remove_urls_and_reasons.keys()).delete()
            RemovedFeed.objects.bulk_create(
                (
                    RemovedFeed(feed_url=url, reason=reason)
                    for url, reason in remove_urls_and_reasons.values()
                ),
                batch_size=1024,
                ignore_conflicts=True,
            )

        return True, HttpResponseRedirect(request.get_full_path())
    else:
        return False, _remove_feeds_render(
            request, formset, request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
        )


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
            return self._remove_feeds__action_end(request, queryset)
        else:
            return self._remove_feeds__action_begin(request, queryset)

    def _remove_feeds__action_formset(
        self, queryset: QuerySet[FeedReport], query_post: QueryDict | None = None
    ):
        initial: list[dict[str, Any]] = []

        for feed in Feed.objects.filter(uuid__in=queryset.values("feed_id")):
            known_reasons: set[str] = set()

            known_reasons.update(
                FeedEntryReport.objects.filter(feed_entry__feed=feed)
                .exclude(reason="")
                .values_list("reason", flat=True)
            )
            known_reasons.update(
                FeedReport.objects.filter(feed=feed)
                .exclude(reason="")
                .values_list("reason", flat=True)
            )

            initial.append(
                {
                    "feed_id": str(feed.uuid),
                    "reason": "",
                    "feed_title": feed.title,
                    "feed_url": feed.feed_url,
                    "known_reasons": list(known_reasons),
                }
            )

        return RemoveFeedsFormset(query_post, initial=initial)

    def _remove_feeds__action_begin(
        self, request: HttpRequest, queryset: QuerySet[FeedReport]
    ) -> HttpResponse:
        selected_action_uuids: set[uuid.UUID] = set()

        for feed_report in queryset.select_related("feed"):
            selected_action_uuids.add(feed_report.uuid)

        return _remove_feeds_render(
            request,
            self._remove_feeds__action_formset(queryset),
            [str(uuid_) for uuid_ in selected_action_uuids],
        )

    def _remove_feeds__action_end(
        self, request: HttpRequest, queryset: QuerySet[FeedReport]
    ) -> HttpResponse:
        formset = self._remove_feeds__action_formset(queryset, request.POST)
        success, response = _remove_feeds(request, formset)
        if success:
            self.message_user(request, f"You validated {len(formset)} feed reports")

        return response


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
            return self._remove_feeds__action_end(request, queryset)
        else:
            return self._remove_feeds__action_begin(request, queryset)

    def _remove_feeds__action_formset(
        self, queryset: QuerySet[FeedEntryReport], query_post: QueryDict | None = None
    ):
        initial: list[dict[str, Any]] = []

        for feed in Feed.objects.filter(
            uuid__in=queryset.values("feed_entry__feed_id")
        ):
            known_reasons: set[str] = set()

            known_reasons.update(
                FeedEntryReport.objects.filter(feed_entry__feed=feed)
                .exclude(reason="")
                .values_list("reason", flat=True)
            )
            known_reasons.update(
                FeedReport.objects.filter(feed=feed)
                .exclude(reason="")
                .values_list("reason", flat=True)
            )

            initial.append(
                {
                    "feed_id": str(feed.uuid),
                    "reason": "",
                    "feed_title": feed.title,
                    "feed_url": feed.feed_url,
                    "known_reasons": list(known_reasons),
                }
            )

        return RemoveFeedsFormset(query_post, initial=initial)

    def _remove_feeds__action_begin(
        self, request: HttpRequest, queryset: QuerySet[FeedEntryReport]
    ) -> HttpResponse:
        selected_action_uuids: set[uuid.UUID] = set()

        for feed_report in queryset.select_related("feed"):
            selected_action_uuids.add(feed_report.uuid)

        return _remove_feeds_render(
            request,
            self._remove_feeds__action_formset(queryset),
            [str(uuid_) for uuid_ in selected_action_uuids],
        )

    def _remove_feeds__action_end(
        self, request: HttpRequest, queryset: QuerySet[FeedEntryReport]
    ) -> HttpResponse:
        formset = self._remove_feeds__action_formset(queryset, request.POST)
        success, response = _remove_feeds(request, formset)
        if success:
            self.message_user(request, f"You validated {len(formset)} feed reports")

        return response


@admin.register(RemovedFeed)
class RemovedFeedAdmin(admin.ModelAdmin):
    pass
