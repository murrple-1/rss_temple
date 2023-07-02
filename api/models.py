import re
import uuid
from collections import defaultdict
from functools import cached_property
from typing import Collection

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import connection, models
from django.db.models.functions import Now
from django.db.models.query_utils import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager["User"]):
    def create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    attributes = models.JSONField(null=False, default=dict)
    subscribed_feeds = models.ManyToManyField(
        "Feed", through="SubscribedFeedUserMapping", related_name="subscribed_user_set"
    )
    read_feed_entries = models.ManyToManyField(
        "FeedEntry", through="ReadFeedEntryUserMapping", related_name="read_user_set"
    )
    favorite_feed_entries = models.ManyToManyField(
        "FeedEntry", related_name="favorite_user_set"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    _google_login: "GoogleLogin | None"
    _facebook_login: "FacebookLogin | None"

    def category_dict(self):
        category_dict: dict[uuid.UUID | None, list[Feed]] | None = getattr(
            self, "_category_dict", None
        )
        if category_dict is None:
            category_dict = defaultdict(list)

            for (
                subscribed_feed_user_mapping
            ) in SubscribedFeedUserMapping.objects.select_related("feed").filter(
                user=self
            ):
                user_category_uuids = frozenset(
                    subscribed_feed_user_mapping.feed.user_categories.values_list(
                        "uuid", flat=True
                    )
                )

                keys: Collection[uuid.UUID | None]
                if len(user_category_uuids) > 0:
                    keys = user_category_uuids
                else:
                    keys = [None]

                feed = subscribed_feed_user_mapping.feed

                feed.custom_title = subscribed_feed_user_mapping.custom_feed_title

                for key in keys:
                    category_dict[key].append(feed)

            self._category_dict = category_dict

        return category_dict

    @cached_property
    def subscribed_feed_uuids(self):
        return frozenset(self.subscribed_feeds.values_list("uuid", flat=True))

    @cached_property
    def read_feed_entry_uuids(self):
        return frozenset(self.read_feed_entries.values_list("uuid", flat=True))

    @cached_property
    def favorite_feed_entry_uuids(self):
        return frozenset(self.favorite_feed_entries.values_list("uuid", flat=True))

    def google_login(self):
        if not hasattr(self, "_google_login"):
            try:
                self._google_login = GoogleLogin.objects.get(user=self)
            except GoogleLogin.DoesNotExist:
                self._google_login = None

        return self._google_login

    def facebook_login(self):
        if not hasattr(self, "_facebook_login"):
            try:
                self._facebook_login = FacebookLogin.objects.get(user=self)
            except FacebookLogin.DoesNotExist:
                self._facebook_login = None

        return self._facebook_login


class AuthToken(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    expires_at = models.DateTimeField(null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_sessions"
    )

    def id_str(self) -> str:
        return str(self.uuid)

    @staticmethod
    def extract_id_from_authorization_header(authorization_header: str) -> "uuid.UUID":
        if match := re.search(
            r"^Bearer ([0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12})$",
            authorization_header,
        ):
            return uuid.UUID(match.group(1))
        else:
            raise ValueError("malformed Authorization header")


class Login(models.Model):
    class Meta:
        abstract = True

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


class GoogleLogin(Login):
    g_user_id = models.CharField(max_length=96)


class FacebookLogin(Login):
    profile_id = models.CharField(max_length=96)


class VerificationToken(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    expires_at = models.DateTimeField()
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def token_str(self):
        return str(self.uuid)

    @staticmethod
    def find_by_token(token):
        _uuid: uuid.UUID
        try:
            _uuid = uuid.UUID(token)
        except (ValueError, TypeError):
            return None

        try:
            return VerificationToken.objects.get(uuid=_uuid, expires_at__gt=Now())
        except VerificationToken.DoesNotExist:
            return None


class PasswordResetToken(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    expires_at = models.DateTimeField()
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def token_str(self):
        return str(self.uuid)

    @staticmethod
    def find_by_token(token):
        _uuid: uuid.UUID
        try:
            _uuid = uuid.UUID(token)
        except (ValueError, TypeError):
            return None

        try:
            return PasswordResetToken.objects.get(uuid=_uuid, expires_at__gt=Now())
        except PasswordResetToken.DoesNotExist:
            return None


class UserCategory(models.Model):
    class Meta:
        unique_together = (("user", "text"),)

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_categories",
    )
    text = models.TextField()
    feeds = models.ManyToManyField("Feed", related_name="user_categories")

    @cached_property
    def feed_uuids(self):
        return self.feeds.values_list("uuid", flat=True)

    def __str__(self) -> str:
        return f"{self.text}"


class Feed(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["update_backoff_until"]),
        ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed_url = models.TextField(unique=True)
    title = models.TextField()
    home_url = models.TextField(null=True)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True)
    db_created_at = models.DateTimeField(default=timezone.now)
    db_updated_at = models.DateTimeField(null=True)
    update_backoff_until = models.DateTimeField(default=timezone.now)

    @staticmethod
    def annotate_search_vectors(qs: models.QuerySet["Feed"]):
        if connection.vendor == "postgresql":  # pragma: no cover
            from django.contrib.postgres.search import SearchVector

            qs = qs.annotate(title_search_vector=SearchVector("title"))

        return qs

    @staticmethod
    def annotate_subscription_data(qs: models.QuerySet["Feed"], user: User):
        subscribed_user_feed_mappings = SubscribedFeedUserMapping.objects.filter(
            user=user, feed_id=models.OuterRef("uuid")
        )
        return qs.annotate(
            custom_title=models.Subquery(
                subscribed_user_feed_mappings.values("custom_feed_title")
            ),
            is_subscribed=models.Exists(subscribed_user_feed_mappings),
        )

    def with_subscription_data(self):
        self.custom_title = None
        self.is_subscribed = False

    @staticmethod
    def _generate_counts(feed, user):
        total_feed_entry_count = feed.feed_entries.count()
        read_count = ReadFeedEntryUserMapping.objects.filter(
            feed_entry__feed=feed, user=user
        ).count()
        unread_count = total_feed_entry_count - read_count

        counts = {
            "unread_count": unread_count,
            "read_count": read_count,
        }

        return counts

    def _counts(self, user):
        counts = getattr(self, "_counts_", None)
        if counts is None:
            counts = Feed._generate_counts(self, user)
            self._counts_ = counts

        return counts

    def unread_count(self, user):
        return self._counts(user)["unread_count"]

    def read_count(self, user):
        return self._counts(user)["read_count"]

    def __str__(self) -> str:
        return f"{self.title} - {self.feed_url} - {self.uuid}"


class SubscribedFeedUserMapping(models.Model):
    class Meta:
        unique_together = (("user", "feed"), ("user", "custom_feed_title"))

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    custom_feed_title = models.TextField(null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


class FeedEntry(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["id"]),
            models.Index(fields=["url"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["feed", "url"],
                name="unique__feed__url__when__updated_at__null",
                condition=Q(updated_at__isnull=True),
            ),
            models.UniqueConstraint(
                fields=["feed", "url", "updated_at"],
                name="unique__feed__url__when__updated_at__not_null",
            ),
        ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    id = models.TextField(null=True)
    feed = models.ForeignKey(
        Feed, on_delete=models.CASCADE, related_name="feed_entries"
    )
    created_at = models.DateTimeField(null=True)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True)
    title = models.TextField()
    url = models.TextField()
    content = models.TextField()
    author_name = models.TextField(null=True)
    db_created_at = models.DateTimeField(default=timezone.now)
    db_updated_at = models.DateTimeField(null=True)

    @staticmethod
    def annotate_search_vectors(qs):
        if connection.vendor == "postgresql":  # pragma: no cover
            from django.contrib.postgres.search import SearchVector

            qs = qs.annotate(
                title_search_vector=SearchVector("title"),
                content_search_vector=SearchVector("content"),
            )

        return qs

    def from_subscription(self, user):
        from_subscription = getattr(self, "_from_subscription", None)
        if from_subscription is None:
            from_subscription = self.feed_id in user.subscribed_feed_uuids
            self._from_subscription = from_subscription

        return from_subscription

    def is_read(self, user):
        is_read = getattr(self, "_is_read", None)
        if is_read is None:
            is_read = self.uuid in user.read_feed_entry_uuids
            self._is_read = is_read

        return is_read

    def is_favorite(self, user):
        is_favorite = getattr(self, "_is_favorite", None)
        if is_favorite is None:
            is_favorite = self.uuid in user.favorite_feed_entry_uuids
            self._is_favorite = is_favorite

        return is_favorite

    def __str__(self) -> str:
        return f"{self.title} - {self.url}"


class ReadFeedEntryUserMapping(models.Model):
    class Meta:
        unique_together = ("feed_entry", "user")

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed_entry = models.ForeignKey(FeedEntry, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(default=timezone.now)


class FeedSubscriptionProgressEntry(models.Model):
    NOT_STARTED = 0
    STARTED = 1
    FINISHED = 2

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.IntegerField(
        default=NOT_STARTED,
        choices=[
            (NOT_STARTED, "Not Started"),
            (STARTED, "Started"),
            (FINISHED, "Finished"),
        ],
    )


class FeedSubscriptionProgressEntryDescriptor(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed_subscription_progress_entry = models.ForeignKey(
        FeedSubscriptionProgressEntry, on_delete=models.CASCADE
    )
    feed_url = models.TextField()
    custom_feed_title = models.TextField(null=True)
    user_category_text = models.TextField(null=True)
    is_finished = models.BooleanField(default=False)


class NotifyEmailQueueEntry(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    subject = models.CharField(max_length=256)
    plain_text = models.TextField(null=True)
    html_text = models.TextField(null=True)


class NotifyEmailQueueEntryRecipient(models.Model):
    TYPE_TO = 0
    TYPE_CC = 1
    TYPE_BCC = 2

    TYPE_CHOICES = (
        (TYPE_TO, "To"),
        (TYPE_CC, "CC"),
        (TYPE_BCC, "BCC"),
    )

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    type = models.IntegerField(choices=TYPE_CHOICES)
    email = models.CharField(max_length=256)
    entry = models.ForeignKey(NotifyEmailQueueEntry, on_delete=models.CASCADE)
