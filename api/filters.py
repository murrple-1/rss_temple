import datetime

from django.db import connection
from django.db.models import Q, QuerySet
from django_filters import rest_framework as filters

from api.models import (
    Feed,
    FeedEntry,
    ReadFeedEntryUserMapping,
    SubscribedFeedUserMapping,
)


class UUIDInFilter(filters.BaseInFilter, filters.UUIDFilter):
    pass


class UserCategoryFilter(filters.FilterSet):
    uuid = UUIDInFilter(field_name="uuid", lookup_expr="in")
    text = filters.CharFilter(field_name="text", lookup_expr="icontains")
    text_exact = filters.CharFilter(field_name="text", lookup_expr="iexact")

    order = filters.OrderingFilter(
        fields=(
            ("uuid", "uuid"),
            ("text", "text"),
        ),
        field_labels={
            "uuid": "UUID",
            "text": "Text",
        },
    )


class FeedFilter(filters.FilterSet):
    uuid = UUIDInFilter(field_name="uuid")
    title = filters.CharFilter(method="filter_title")
    title_exact = filters.CharFilter(field_name="text", lookup_expr="iexact")
    feedUrl = filters.CharFilter(field_name="feed_url", lookup_expr="iexact")
    homeUrl = filters.CharFilter(field_name="home_url", lookup_expr="iexact")
    publishedAt = filters.IsoDateTimeFromToRangeFilter(field_name="published_at")
    publishedAt_exact = filters.IsoDateTimeFilter(
        field_name="published_at", lookup_expr="exact"
    )
    updatedAt = filters.IsoDateTimeFromToRangeFilter(field_name="updated_at")
    updatedAt_exact = filters.IsoDateTimeFilter(
        field_name="updated_at", lookup_expr="exact"
    )
    subscribed = filters.BooleanFilter(field_name="is_subscribed", lookup_expr="exact")
    customTitle = filters.CharFilter(field_name="custom_title", lookup_expr="icontains")
    customTitle_exact = filters.CharFilter(
        field_name="custom_title", lookup_expr="iexact"
    )
    customTitle_null = filters.BooleanFilter(
        field_name="custom_title", lookup_expr="isnull"
    )
    calculatedTitle = filters.CharFilter(method="filter_calculatedTitle")
    calculatedTitle_exact = filters.CharFilter(method="filter_calculatedTitle_exact")

    def filter_title(self, queryset: QuerySet[Feed], name: str, value: str):
        if connection.vendor == "postgresql":
            return queryset.filter(Q(title_search_vector=value))
        else:
            return queryset.filter(Q(title__icontains=value))

    def filter_calculatedTitle(self, queryset: QuerySet[Feed], name: str, value: str):
        return queryset.filter(
            Q(title__icontains=value) | Q(custom_title__icontains=value)
        )

    def filter_calculatedTitle_exact(
        self, queryset: QuerySet[Feed], name: str, value: str
    ):
        return queryset.filter(Q(title__iexact=value) | Q(custom_title__iexact=value))

    order = filters.OrderingFilter(
        fields=(
            ("uuid", "uuid"),
            ("title", "title"),
            ("feed_url", "feedUrl"),
            ("home_url", "homeUrl"),
            ("published_at", "publishedAt"),
            ("updated_at", "updatedAt"),
            ("is_subscribed", "subscribed"),
            ("custom_title", "customTitle"),
        ),
        field_labels={
            "uuid": "UUID",
            "title": "Title",
            "feed_url": "Feed URL",
            "home_url": "Home URL",
            "published_at": "Published At",
            "updated_at": "Updated At",
            "is_subscribed": "Is Subscribed",
            "custom_title": "Custom Title",
        },
    )


class FeedEntryFilter(filters.FilterSet):
    uuid = UUIDInFilter(field_name="uuid")
    title = filters.CharFilter(method="filter_title")
    title_exact = filters.CharFilter(field_name="text", lookup_expr="iexact")
    content = filters.CharFilter(method="filter_content")
    feedUuid = UUIDInFilter(field_name="feed_id")
    feedUrl = filters.CharFilter(field_name="feed__feed_url", lookup_expr="iexact")
    createdAt = filters.IsoDateTimeFromToRangeFilter(field_name="created_at")
    createdAt_exact = filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="exact"
    )
    publishedAt = filters.IsoDateTimeFromToRangeFilter(field_name="published_at")
    publishedAt_exact = filters.IsoDateTimeFilter(
        field_name="published_at", lookup_expr="exact"
    )
    updatedAt = filters.IsoDateTimeFromToRangeFilter(field_name="updated_at")
    updatedAt_exact = filters.IsoDateTimeFilter(
        field_name="updated_at", lookup_expr="exact"
    )
    url = filters.CharFilter(field_name="url", lookup_expr="iexact")
    authorName = filters.CharFilter(field_name="author_name", lookup_expr="icontains")
    authorName_exact = filters.CharFilter(
        field_name="author_name", lookup_expr="iexact"
    )
    subscribed = filters.BooleanFilter(method="filter_subscribed")
    isRead = filters.BooleanFilter(method="filter_isRead")
    isFavorite = filters.BooleanFilter(method="filter_isFavorite")
    readAt = filters.IsoDateTimeFromToRangeFilter(method="filter_readAt")
    readAt_exact = filters.IsoDateTimeFilter(method="filter_readAt_exact")

    def filter_title(self, queryset: QuerySet[FeedEntry], name: str, value: str):
        if connection.vendor == "postgresql":
            return queryset.filter(Q(title_search_vector=value))
        else:
            return queryset.filter(Q(title__icontains=value))

    def filter_content(self, queryset: QuerySet[FeedEntry], name: str, value: str):
        if connection.vendor == "postgresql":
            return queryset.filter(Q(content_search_vector=value))
        else:
            return queryset.filter(Q(content__icontains=value))

    def filter_subscribed(self, queryset: QuerySet[FeedEntry], name: str, value: bool):
        user = getattr(self.request, "user", None)
        if user is None:
            return queryset

        q = Q(
            feed__in=Feed.objects.filter(
                uuid__in=SubscribedFeedUserMapping.objects.filter(user=user).values(
                    "feed_id"
                )
            )
        )

        if not value:
            q = ~q

        return queryset.filter(q)

    def filter_isRead(self, queryset: QuerySet[FeedEntry], name: str, value: bool):
        user = getattr(self.request, "user", None)
        if user is None:
            return queryset

        q = Q(
            uuid__in=ReadFeedEntryUserMapping.objects.filter(user=user).values(
                "feed_entry_id"
            )
        )

        if not value:
            q = ~q

        return queryset.filter(q)

    def filter_isFavorite(self, queryset: QuerySet[FeedEntry], name: str, value: bool):
        user = getattr(self.request, "user", None)
        if user is None:
            return queryset

        q = Q(uuid__in=user.favorite_feed_entries.values("id"))

        if not value:
            q = ~q

        return queryset.filter(q)

    def filter_readAt(
        self,
        queryset: QuerySet[FeedEntry],
        name: str,
        value: tuple[datetime.datetime, datetime.datetime],
    ):
        user = getattr(self.request, "user", None)
        if user is None:
            return queryset

        return queryset.filter(
            Q(
                uuid__in=ReadFeedEntryUserMapping.objects.filter(
                    user=user,
                    read_at__range=value,
                )
            )
        )

    def filter_readAt_exact(
        self, queryset: QuerySet[FeedEntry], name: str, value: datetime.datetime
    ):
        user = getattr(self.request, "user", None)
        if user is None:
            return queryset

        return queryset.filter(
            Q(
                uuid__in=ReadFeedEntryUserMapping.objects.filter(
                    user=user, read_at=value
                )
            )
        )

    order = filters.OrderingFilter(
        fields=(
            ("uuid", "uuid"),
            ("title", "title"),
            ("created_at", "createdAt"),
            ("published_at", "publishedAt"),
            ("updated_at", "updatedAt"),
        ),
        field_labels={
            "uuid": "UUID",
            "title": "Title",
            "created_at": "Created At",
            "published_at": "Published At",
            "updated_at": "Updated At",
        },
    )
