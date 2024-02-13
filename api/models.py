import random
import uuid as uuid_
from collections import defaultdict
from functools import cached_property
from typing import TYPE_CHECKING, Collection, NamedTuple, Sequence

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import connection, models
from django.utils import timezone
from rest_framework.authtoken.models import Token as _Token

from api.captcha import ALPHABET as CAPTCHA_ALPHABET

if TYPE_CHECKING:  # pragma: no cover
    from api.cache_utils.subscription_datas import SubscriptionData


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
    text = models.CharField(max_length=1024)
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
    feed_url = models.URLField(max_length=2048, unique=True)
    title = models.TextField()
    home_url = models.URLField(max_length=2048, null=True)
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

    @staticmethod
    def annotate_subscription_data__case(
        qs: models.QuerySet["Feed"], subscription_datas: Sequence["SubscriptionData"]
    ) -> models.QuerySet["Feed"]:
        subscribed_uuids = [sd["uuid"] for sd in subscription_datas]
        custom_title_case_whens: list[models.When] = [
            models.When(
                condition=models.Q(uuid=sd["uuid"]),
                then=models.Value(sd["custom_title"]),
            )
            for sd in subscription_datas
        ]

        return qs.annotate(
            custom_title=models.Case(
                *custom_title_case_whens,
                output_field=models.CharField(null=True),
            ),
            is_subscribed=models.Case(
                models.When(
                    condition=models.Q(uuid__in=subscribed_uuids),
                    then=models.Value(True),
                ),
                default=models.Value(False),
                output_field=models.BooleanField(),
            ),
        )

    def with_subscription_data(self) -> None:
        self.custom_title = None
        self.is_subscribed = False

    class _CountsDescriptor(NamedTuple):
        unread_count: int
        read_count: int

    @staticmethod
    def generate_counts(feed_uuid: uuid_.UUID, user: User) -> _CountsDescriptor:
        counts = Feed.objects.filter(uuid=feed_uuid).aggregate(
            total_count=models.Count("feed_entries__uuid"),
            unread_count=models.Count(
                "feed_entries__uuid",
                filter=(
                    models.Q(feed_entries__is_archived=False)
                    & ~models.Q(
                        feed_entries__uuid__in=ReadFeedEntryUserMapping.objects.filter(
                            user=user, feed_entry__feed_id=feed_uuid
                        ).values("feed_entry_id")
                    )
                ),
            ),
        )
        total_count: int = counts["total_count"]
        unread_count: int = counts["unread_count"]

        read_count = total_count - unread_count

        return Feed._CountsDescriptor(unread_count, read_count)

    @staticmethod
    def generate_counts_lookup(
        user: User, feed_uuids: Collection[uuid_.UUID]
    ) -> dict[uuid_.UUID, _CountsDescriptor]:
        feed_uuids = frozenset(feed_uuids)
        return {
            r["uuid"]: Feed._CountsDescriptor(
                r["unread_count"], r["total_count"] - r["unread_count"]
            )
            for r in Feed.objects.filter(uuid__in=feed_uuids)
            .values("uuid")
            .annotate(
                total_count=models.Count("feed_entries__uuid"),
                unread_count=models.Count(
                    "feed_entries__uuid",
                    filter=(
                        models.Q(feed_entries__is_archived=False)
                        & ~models.Q(
                            feed_entries__uuid__in=ReadFeedEntryUserMapping.objects.filter(
                                user=user,
                                feed_entry__feed_id__in=feed_uuids,
                            ).values(
                                "feed_entry_id"
                            )
                        )
                    ),
                ),
            )
            .values("uuid", "total_count", "unread_count")
        }

    def _counts(self, user: User) -> _CountsDescriptor:
        counts = getattr(self, "_counts_", None)
        if counts is None:
            counts = Feed.generate_counts(self.uuid, user)
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
    feed_url = models.URLField(max_length=2048, unique=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)


class DuplicateFeedSuggestion(models.Model):
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~models.Q(feed1_id__lt=models.F("feed2_id")),
                name="duplicatefeedsuggestion__check__feed1_id__feed2_id__lessthan",
            ),
            models.UniqueConstraint(
                fields=("feed1", "feed2"),
                name="duplicatefeedsuggestion__unique__feed1__feed2",
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
            models.UniqueConstraint(
                fields=("user", "feed"),
                name="subscribedfeedusermapping__unique__user__feed",
            ),
            models.UniqueConstraint(
                fields=("user", "custom_feed_title"),
                name="subscribedfeedusermapping__unique__user__custom_feed_title",
            ),
        )

    uuid = models.UUIDField(primary_key=True, default=uuid_.uuid4)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    custom_feed_title = models.CharField(max_length=1024, null=True)
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
    id = models.CharField(max_length=2048, null=True)
    feed = models.ForeignKey(
        Feed, on_delete=models.CASCADE, related_name="feed_entries"
    )
    created_at = models.DateTimeField(null=True)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True)
    title = models.TextField()
    url = models.URLField(max_length=2048)
    content = models.TextField()
    author_name = models.CharField(max_length=1024, null=True)
    db_created_at = models.DateTimeField(default=timezone.now)
    db_updated_at = models.DateTimeField(null=True)
    is_archived = models.BooleanField(default=False)
    language = models.ForeignKey(
        Language, related_name="feed_entries", null=True, on_delete=models.SET_NULL
    )
    has_top_image_been_processed = models.BooleanField(default=False)
    top_image_src = models.URLField(max_length=2048, default="")
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

    is_from_subscription: bool
    is_read: bool
    is_favorite: bool

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

    @staticmethod
    def annotate_user_data(
        qs: models.QuerySet["FeedEntry"], user: User
    ) -> models.QuerySet["FeedEntry"]:
        subscribed_user_feed_mappings = SubscribedFeedUserMapping.objects.filter(
            user=user, feed_id=models.OuterRef("feed_id")
        )
        read_user_feed_entry_mapping = ReadFeedEntryUserMapping.objects.filter(
            user=user, feed_entry_id=models.OuterRef("uuid")
        )
        favorite_user_feed_entry_mapping = (
            User.favorite_feed_entries.through.objects.filter(
                user=user, feedentry_id=models.OuterRef("uuid")
            )
        )
        return qs.annotate(
            is_from_subscription=models.Exists(subscribed_user_feed_mappings),
            is_read=models.Q(is_archived=True)
            | models.Exists(read_user_feed_entry_mapping),
            is_favorite=models.Exists(favorite_user_feed_entry_mapping),
        )

    @staticmethod
    def annotate_user_data__case(
        qs: models.QuerySet["FeedEntry"],
        subscription_datas: Sequence["SubscriptionData"],
        read_feed_entry_uuids: Sequence[uuid_.UUID],
        favorite_feed_entry_uuids: Sequence[uuid_.UUID],
    ) -> models.QuerySet["FeedEntry"]:
        subscribed_uuids = [sd["uuid"] for sd in subscription_datas]

        return qs.annotate(
            is_subscribed=models.Case(
                models.When(
                    condition=models.Q(feed_id__in=subscribed_uuids),
                    then=models.Value(True),
                ),
                default=models.Value(False),
                output_field=models.BooleanField(),
            ),
            is_read=models.Q(is_archived=True)
            | models.Case(
                models.When(
                    condition=models.Q(feed_id__in=read_feed_entry_uuids),
                    then=models.Value(True),
                ),
                default=models.Value(False),
                output_field=models.BooleanField(),
            ),
            is_favorite=models.Case(
                models.When(
                    condition=models.Q(feed_id__in=favorite_feed_entry_uuids),
                    then=models.Value(True),
                ),
                default=models.Value(False),
                output_field=models.BooleanField(),
            ),
        )

    def with_user_data(self):
        self.is_from_subscription = False
        self.is_read = False
        self.is_favorite = False

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
    feed_url = models.URLField(max_length=2048)
    custom_feed_title = models.CharField(max_length=1024, null=True)
    user_category_text = models.CharField(max_length=1024, null=True)
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
