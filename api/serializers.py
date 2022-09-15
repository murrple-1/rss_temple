import datetime

from django.conf import settings
from django.core.signals import setting_changed
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from drf_queryfields import QueryFieldsMixin
from rest_framework import serializers

from api.exceptions import Conflict
from api.models import (
    Feed,
    FeedEntry,
    NotifyEmailQueueEntry,
    NotifyEmailQueueEntryRecipient,
    User,
    UserCategory,
    VerificationToken,
)
from api.render import verify as verifyrender

_USER_VERIFICATION_EXPIRY_INTERVAL: datetime.datetime


@receiver(setting_changed)
def _load_global_settings(*args, **kwargs):
    global _USER_VERIFICATION_EXPIRY_INTERVAL

    _USER_VERIFICATION_EXPIRY_INTERVAL = settings.USER_VERIFICATION_EXPIRY_INTERVAL


_load_global_settings()


class UserFilteredPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        request = self.context.get("request", None)
        queryset = super().get_queryset()
        if not request or not queryset:
            return None
        return queryset.filter(user=request.user)


class UserSerializer(QueryFieldsMixin, serializers.ModelSerializer[User]):
    include_arg_name = "include"
    exclude_arg_name = "exclude"

    email = serializers.EmailField(required=False)
    subscribedFeedUuids = UserFilteredPrimaryKeyRelatedField(
        source="subscribed_feeds",
        many=True,
        read_only=True,
        pk_field=serializers.UUIDField(),
    )

    class Meta:
        model = User
        fields = ["uuid", "email", "attributes", "subscribedFeedUuids"]
        read_only_fields = ["uuid", "attributes"]

    def update(self, instance: User, validated_data):
        email = validated_data.get("email")
        verification_token: VerificationToken | None = None
        if email:
            if instance.email != email:
                if User.objects.filter(email=email).exists():
                    raise Conflict("email already in use")

                instance.email = email

                verification_token = VerificationToken(
                    user=instance,
                    expires_at=(timezone.now() + _USER_VERIFICATION_EXPIRY_INTERVAL),
                )

        with transaction.atomic():
            instance.save()

            if email and verification_token:
                VerificationToken.objects.filter(user=instance).delete()
                verification_token.save()

                token_str = verification_token.token_str

                subject = verifyrender.subject()
                plain_text = verifyrender.plain_text(token_str)
                html_text = verifyrender.html_text(token_str)

                email_queue_entry = NotifyEmailQueueEntry.objects.create(
                    subject=subject, plain_text=plain_text, html_text=html_text
                )
                NotifyEmailQueueEntryRecipient.objects.create(
                    type=NotifyEmailQueueEntryRecipient.TYPE_TO,
                    email=email,
                    entry=email_queue_entry,
                )

        return instance


class UserCategorySerializer(
    QueryFieldsMixin, serializers.ModelSerializer[UserCategory]
):
    include_arg_name = "include"
    exclude_arg_name = "exclude"

    feedUuids = UserFilteredPrimaryKeyRelatedField(
        source="feeds",
        many=True,
        read_only=True,
        pk_field=serializers.UUIDField(),
    )

    class Meta:
        model = UserCategory
        fields = ["uuid", "text", "feedUuids"]
        read_only_fields = ["uuid"]

    def create(self, validated_date):
        request = self.context.get("request")
        if request:
            validated_date["user"] = request.user

        return super().create(validated_date)


class FeedSerializer(QueryFieldsMixin, serializers.ModelSerializer[Feed]):
    include_arg_name = "include"
    exclude_arg_name = "exclude"

    feedUrl = serializers.CharField(source="feed_url")
    homeUrl = serializers.CharField(source="home_url")
    publishedAt = serializers.DateTimeField(source="published_at")
    updatedAt = serializers.DateTimeField(source="updated_at")
    subscribed = serializers.BooleanField(source="is_subscribed")
    customTitle = serializers.CharField(source="custom_title")
    userCategoryUuids = UserFilteredPrimaryKeyRelatedField(
        source="user_categories",
        many=True,
        read_only=True,
        pk_field=serializers.UUIDField(),
    )
    readCount = serializers.SerializerMethodField(method_name="get_read_count")
    unreadCount = serializers.SerializerMethodField(method_name="get_unread_count")

    class Meta:
        model = Feed
        fields = [
            "uuid",
            "title",
            "feedUrl",
            "homeUrl",
            "publishedAt",
            "updatedAt",
            "subscribed",
            "customTitle",
            "userCategoryUuids",
            "readCount",
            "unreadCount",
        ]
        read_only_fields = [
            "uuid",
            "title",
            "feedUrl",
            "homeUrl",
            "publishedAt",
            "updatedAt",
            "subscribed",
            "customTitle",
            "userCategoryUuids",
            "readCount",
            "unreadCount",
        ]

    def get_read_count(self, obj: Feed):
        request = self.context.get("request")
        if not request:
            return None

        return obj.read_count(request.user)

    def get_unread_count(self, obj: Feed):
        request = self.context.get("request")
        if not request:
            return None

        return obj.unread_count(request.user)


class FeedEntrySerializer(QueryFieldsMixin, serializers.ModelSerializer[FeedEntry]):
    include_arg_name = "include"
    exclude_arg_name = "exclude"

    createdAt = serializers.DateTimeField(source="created_at")
    publishedAt = serializers.DateTimeField(source="published_at")
    updatedAt = serializers.DateTimeField(source="updated_at")
    authorName = serializers.CharField(source="author_name")
    feedUuid = serializers.PrimaryKeyRelatedField(
        source="feed",
        read_only=True,
        pk_field=serializers.UUIDField(),
    )
    fromSubscription = serializers.SerializerMethodField(
        method_name="get_from_subscription"
    )
    isRead = serializers.SerializerMethodField(method_name="get_is_read")
    isFavorite = serializers.SerializerMethodField(method_name="get_is_favorite")
    readAt = serializers.SerializerMethodField(method_name="get_read_at")

    class Meta:
        model = FeedEntry
        fields = [
            "uuid",
            "id",
            "title",
            "url",
            "content",
            "createdAt",
            "publishedAt",
            "updatedAt",
            "authorName",
            "feedUuid",
            "fromSubscription",
            "isRead",
            "isFavorite",
            "readAt",
        ]
        read_only_fields = [
            "uuid",
            "id",
            "title",
            "url",
            "content",
            "createdAt",
            "publishedAt",
            "updatedAt",
            "authorName",
            "feedUuid",
            "fromSubscription",
            "isRead",
            "isFavorite",
            "readAt",
        ]

    def get_from_subscription(self, obj: FeedEntry):
        request = self.context.get("request")
        if not request:
            return False

        return request.user.subscribed_feeds.filter(uuid=obj.feed_id).exists()

    def get_is_read(self, obj: FeedEntry):
        request = self.context.get("request")
        if not request:
            return False

        return request.user.read_feed_entries.filter(uuid=obj.uuid).exists()

    def get_is_favorite(self, obj: FeedEntry):
        request = self.context.get("request")
        if not request:
            return False

        return request.user.favorite_feed_entries.filter(uuid=obj.uuid).exists()

    def get_read_at(self, obj: FeedEntry):
        request = self.context.get("request")
        if not request:
            return None

        try:
            return request.user.read_feed_entries.get(
                uuid=obj.uuid
            ).readfeedentryusermapping.read_at
        except FeedEntry.DoesNotExist:
            return None
