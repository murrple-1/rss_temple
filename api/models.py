import random
import uuid as uuid_
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Collection

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import connection, models
from django.utils import timezone
from rest_framework.authtoken.models import Token as _Token

from api.captcha import ALPHABET as CAPTCHA_ALPHABET


class UserManager(BaseUserManager["User"]):
    def create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The Email must be set")
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
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    attributes = models.JSONField(null=False, default=dict)
    subscribed_feeds: models.ManyToManyField = models.ManyToManyField(
        "Feed", through="SubscribedFeedUserMapping", related_name="subscribed_user_set"
    )
    read_feed_entries: models.ManyToManyField = models.ManyToManyField(
        "FeedEntry", through="ReadFeedEntryUserMapping", related_name="read_user_set"
    )
    read_feed_entries_counter = models.PositiveIntegerField(default=0)
    favorite_feed_entries: models.ManyToManyField = models.ManyToManyField(
        "FeedEntry", related_name="favorite_user_set"
    )
    calculated_classifier_labels: models.ManyToManyField = models.ManyToManyField(
        "ClassifierLabel",
        through="ClassifierLabelUserCalculated",
        related_name="calculated_user_set",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def category_dict(self) -> dict[uuid_.UUID | None, list["Feed"]]:
        category_dict: dict[uuid_.UUID | None, list[Feed]] | None = getattr(
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

                keys: Collection[uuid_.UUID | None]
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
    def subscribed_feed_uuids(self) -> frozenset[uuid_.UUID]:
        return frozenset(self.subscribed_feeds.values_list("uuid", flat=True))

    @cached_property
    def read_feed_entry_uuids(self) -> frozenset[uuid_.UUID]:
        return frozenset(self.read_feed_entries.values_list("uuid", flat=True))

    @cached_property
    def favorite_feed_entry_uuids(self) -> frozenset[uuid_.UUID]:
        return frozenset(self.favorite_feed_entries.values_list("uuid", flat=True))


class Token(_Token):
    # overwrite OneToOneField with ForeignKey for multiple tokens per user
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="auth_tokens", on_delete=models.CASCADE
    )  # type: ignore
    expires_at = models.DateTimeField(null=True)


class UserCategory(models.Model):
    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("user", "text"), name="usercategory__unique__user__text"
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_categories",
    )
    text = models.TextField()
    feeds: models.ManyToManyField = models.ManyToManyField(
        "Feed", related_name="user_categories"
    )

    @cached_property
    def feed_uuids(self) -> list[uuid_.UUID]:
        return list(self.feeds.values_list("uuid", flat=True))

    def __str__(self) -> str:
        return f"{self.text}"


class ClassifierLabel(models.Model):
    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("text",),
                name="classifierlabel__unique__text",
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    text = models.CharField(max_length=128)


class ClassifierLabelFeedEntryVote(models.Model):
    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("classifier_label", "feed_entry", "user"),
                name="classifierlabelfeedentryvote__unique__classifier_label__feed_entry__user",
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    classifier_label = models.ForeignKey(ClassifierLabel, on_delete=models.CASCADE)
    feed_entry = models.ForeignKey("FeedEntry", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class ClassifierLabelFeedEntryCalculated(models.Model):
    class Meta:
        indexes = (models.Index(fields=["expires_at"]),)
        constraints = (
            models.UniqueConstraint(
                fields=("classifier_label", "feed_entry"),
                name="classifierlabelfeedentrycalculated__unique__classifier_label__feed_entry",
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    classifier_label = models.ForeignKey(ClassifierLabel, on_delete=models.CASCADE)
    feed_entry = models.ForeignKey("FeedEntry", on_delete=models.CASCADE)
    expires_at = models.DateTimeField()


class ClassifierLabelFeedCalculated(models.Model):
    class Meta:
        indexes = (models.Index(fields=["expires_at"]),)
        constraints = (
            models.UniqueConstraint(
                fields=("classifier_label", "feed"),
                name="classifierlabelfeedcalculated__unique__classifier_label__feed",
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    classifier_label = models.ForeignKey(ClassifierLabel, on_delete=models.CASCADE)
    feed = models.ForeignKey("Feed", on_delete=models.CASCADE)
    expires_at = models.DateTimeField()


class ClassifierLabelUserCalculated(models.Model):
    class Meta:
        indexes = (models.Index(fields=["expires_at"]),)
        constraints = (
            models.UniqueConstraint(
                fields=("classifier_label", "user"),
                name="classifierlabelusercalculated__unique__classifier_label__user",
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    classifier_label = models.ForeignKey(ClassifierLabel, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()


class Language(models.Model):
    iso639_3 = models.CharField(primary_key=True, max_length=3)
    iso639_1 = models.CharField(max_length=2)
    name = models.CharField(max_length=64)


class Feed(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["update_backoff_until"]),
        ]

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    feed_url = models.TextField(unique=True)
    title = models.TextField()
    home_url = models.TextField(null=True)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True)
    db_created_at = models.DateTimeField(default=timezone.now)
    db_updated_at = models.DateTimeField(null=True)
    update_backoff_until = models.DateTimeField(default=timezone.now)
    archive_update_backoff_until = models.DateTimeField(default=timezone.now)
    calculated_classifier_labels: models.ManyToManyField = models.ManyToManyField(
        ClassifierLabel,
        through="ClassifierLabelFeedCalculated",
        related_name="calculated_feed_set",
    )

    custom_title: str | None
    is_subscribed: bool

    @staticmethod
    def annotate_search_vectors(qs: models.QuerySet["Feed"]) -> models.QuerySet["Feed"]:
        if connection.vendor == "postgresql":  # pragma: no cover
            from django.contrib.postgres.search import SearchVector

            qs = qs.annotate(title_search_vector=SearchVector("title"))

        return qs

    @staticmethod
    def annotate_subscription_data(
        qs: models.QuerySet["Feed"], user: User
    ) -> models.QuerySet["Feed"]:
        subscribed_user_feed_mappings = SubscribedFeedUserMapping.objects.filter(
            user=user, feed_id=models.OuterRef("uuid")
        )
        return qs.annotate(
            custom_title=models.Subquery(
                subscribed_user_feed_mappings.values("custom_feed_title")
            ),
            is_subscribed=models.Exists(subscribed_user_feed_mappings),
        )

    def with_subscription_data(self) -> None:
        self.custom_title = None
        self.is_subscribed = False

    @dataclass(slots=True)
    class _CountsDescriptor:
        unread_count: int
        read_count: int

    @staticmethod
    def _generate_counts(feed: "Feed", user: User) -> _CountsDescriptor:
        counts = Feed.objects.filter(uuid=feed.uuid).aggregate(
            total_count=models.Count("feed_entries__uuid"),
            unread_count=models.Count(
                "feed_entries__uuid",
                filter=(
                    models.Q(feed_entries__is_archived=False)
                    & ~models.Q(
                        feed_entries__uuid__in=ReadFeedEntryUserMapping.objects.filter(
                            user=user, feed_entry__feed=feed
                        ).values("feed_entry_id")
                    )
                ),
            ),
        )
        total_count: int = counts["total_count"]
        unread_count: int = counts["unread_count"]

        read_count = total_count - unread_count

        return Feed._CountsDescriptor(unread_count, read_count)

    def _counts(self, user: User) -> _CountsDescriptor:
        counts = getattr(self, "_counts_", None)
        if counts is None:
            counts = Feed._generate_counts(self, user)
            self._counts_ = counts

        return counts

    def unread_count(self, user: User) -> int:
        return self._counts(user).unread_count

    def read_count(self, user: User) -> int:
        return self._counts(user).read_count

    def __str__(self) -> str:
        return f"{self.title} - {self.feed_url} - {self.uuid}"


class AlternateFeedURL(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    feed_url = models.TextField(unique=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)


class DuplicateFeedSuggestion(models.Model):
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~models.Q(feed1_id__lt=models.F("feed2_id")),
                name="check__feed1_id__feed2_id__lessthan",
            ),
            models.UniqueConstraint(
                fields=("feed1", "feed2"), name="unique__feed1__feed2"
            ),
        ]

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    feed1 = models.ForeignKey(
        Feed, on_delete=models.CASCADE, related_name="duplicate_feed_suggestions_1"
    )
    feed2 = models.ForeignKey(
        Feed, on_delete=models.CASCADE, related_name="duplicate_feed_suggestions_2"
    )
    is_ignored = models.BooleanField(default=False)


class SubscribedFeedUserMapping(models.Model):
    class Meta:
        constraints = (
            models.UniqueConstraint(fields=("user", "feed"), name="unique__user__feed"),
            models.UniqueConstraint(
                fields=("user", "custom_feed_title"),
                name="subscribedfeedusermapping__unique__user__custom_feed_title",
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    custom_feed_title = models.TextField(null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


class FeedEntry(models.Model):
    class Meta:
        indexes = (
            models.Index(fields=("-published_at",)),
            models.Index(fields=("is_archived",)),
            models.Index(fields=("has_top_image_been_processed",)),
        )

        constraints = (
            models.UniqueConstraint(
                fields=("feed", "id"),
                name="feedentry__unique__feed__id__when__updated_at__null",
                condition=models.Q(updated_at__isnull=True),
            ),
            models.UniqueConstraint(
                fields=("feed", "id", "updated_at"),
                name="feedentry__unique__feed__id__updated_at",
            ),
            models.UniqueConstraint(
                fields=("feed", "url"),
                name="feedentry__unique__feed__url__when__id__null__updated_at__null",
                condition=models.Q(id__isnull=True, updated_at__isnull=True),
            ),
            models.UniqueConstraint(
                fields=("feed", "url", "updated_at"),
                name="feedentry__unique__feed__url__updated_at__when__id__null",
                condition=models.Q(id__isnull=True),
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
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
    has_top_image_been_processed = models.BooleanField(default=False)
    top_image_src = models.TextField(default="")
    top_image_processing_attempt_count = models.PositiveIntegerField(default=0)
    voted_classifier_labels: models.ManyToManyField = models.ManyToManyField(
        ClassifierLabel,
        through="ClassifierLabelFeedEntryVote",
        related_name="voted_feed_entry_set",
    )
    calculated_classifier_labels: models.ManyToManyField = models.ManyToManyField(
        ClassifierLabel,
        through="ClassifierLabelFeedEntryCalculated",
        related_name="calculated_feed_entry_set",
    )

    @staticmethod
    def annotate_search_vectors(
        qs: models.QuerySet["FeedEntry"],
    ) -> models.QuerySet["FeedEntry"]:
        if connection.vendor == "postgresql":  # pragma: no cover
            from django.contrib.postgres.search import SearchVector

            qs = qs.annotate(
                title_search_vector=SearchVector("title"),
                content_search_vector=SearchVector("content"),
            )

        return qs

    def from_subscription(self, user: User) -> bool:
        from_subscription = getattr(self, "_from_subscription", None)
        if from_subscription is None:
            from_subscription = self.feed_id in user.subscribed_feed_uuids
            self._from_subscription = from_subscription

        return from_subscription

    def is_read(self, user: User) -> bool:
        is_read = getattr(self, "_is_read", None)
        if is_read is None:
            is_read = self.is_archived or self.uuid in user.read_feed_entry_uuids
            self._is_read = is_read

        return is_read

    def is_favorite(self, user: User) -> bool:
        is_favorite = getattr(self, "_is_favorite", None)
        if is_favorite is None:
            is_favorite = self.uuid in user.favorite_feed_entry_uuids
            self._is_favorite = is_favorite

        return is_favorite

    def __str__(self) -> str:
        return f"{self.title} - {self.url}"


class ReadFeedEntryUserMapping(models.Model):
    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("feed_entry", "user"),
                name="readfeedentryusermapping__unique__feed_entry__user",
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    feed_entry = models.ForeignKey(FeedEntry, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(default=timezone.now)


class FeedSubscriptionProgressEntry(models.Model):
    NOT_STARTED = 0
    STARTED = 1
    FINISHED = 2

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
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
    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    feed_subscription_progress_entry = models.ForeignKey(
        FeedSubscriptionProgressEntry, on_delete=models.CASCADE
    )
    feed_url = models.TextField()
    custom_feed_title = models.TextField(null=True)
    user_category_text = models.TextField(null=True)
    is_finished = models.BooleanField(default=False)


class Captcha(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    key = models.CharField(max_length=64, unique=True)
    seed = models.CharField(max_length=64)
    expires_at = models.DateTimeField()

    _random: random.Random | None = None
    _secret_phrase: str | None = None

    def _setup(self) -> None:
        self._random = random.Random(self.seed)
        self._secret_phrase = "".join(
            self._random.choice(CAPTCHA_ALPHABET) for _ in range(6)
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
