import random
import string
import uuid
from collections import defaultdict
from functools import cached_property
from typing import Collection

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import connection, models
from django.db.models.query_utils import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.authtoken.models import Token as _Token


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
    read_feed_entries_counter = models.PositiveIntegerField(default=0)
    favorite_feed_entries = models.ManyToManyField(
        "FeedEntry", related_name="favorite_user_set"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

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


class Token(_Token):
    # overwrite OneToOneField with ForeignKey for multiple tokens per user
    user: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="auth_tokens", on_delete=models.CASCADE
    )
    expires_at = models.DateTimeField(null=True)


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


class Language(models.Model):
    iso639_3 = models.CharField(primary_key=True, max_length=3)
    iso639_1 = models.CharField(max_length=2)
    name = models.CharField(max_length=64)


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
    archive_update_backoff_until = models.DateTimeField(default=timezone.now)

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
    def _generate_counts(feed: "Feed", user: User):
        total_feed_entry_count = feed.feed_entries.count()
        unread_count = (
            feed.feed_entries.filter(is_archived=False)
            .exclude(
                uuid__in=ReadFeedEntryUserMapping.objects.filter(
                    user=user, feed_entry__feed=feed
                ).values("feed_entry_id")
            )
            .count()
        )
        read_count = total_feed_entry_count - unread_count

        counts = {
            "unread_count": unread_count,
            "read_count": read_count,
        }

        return counts

    def _counts(self, user: User):
        counts = getattr(self, "_counts_", None)
        if counts is None:
            counts = Feed._generate_counts(self, user)
            self._counts_ = counts

        return counts

    def unread_count(self, user: User):
        return self._counts(user)["unread_count"]

    def read_count(self, user: User):
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
            models.Index(fields=["-published_at"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["-updated_at"]),
            models.Index(fields=["is_archived"]),
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
    is_archived = models.BooleanField(default=False)
    language = models.ForeignKey(
        Language, related_name="feed_entries", null=True, on_delete=models.SET_NULL
    )

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
            is_read = self.is_archived or self.uuid in user.read_feed_entry_uuids
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


class Captcha(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    key = models.CharField(max_length=64, unique=True)
    seed = models.CharField(max_length=64)
    expires_at = models.DateTimeField()

    _random: random.Random | None = None
    _secret_phrase: str | None = None

    def _setup(self) -> None:
        self._random = random.Random(self.seed)
        self._secret_phrase = "".join(
            self._random.choice(
                string.digits  # TODO include string.ascii_letters when WAV files are ready
            )
            for _ in range(6)
        )

    @property
    def rng(self) -> random.Random:
        if self._random is None:
            self._setup()
        assert self._random is not None
        return self._random

    @property
    def secret_phrase(self) -> str:
        if self._secret_phrase is None:
            self._setup()
        assert self._secret_phrase is not None
        return self._secret_phrase
