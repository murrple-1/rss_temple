import uuid
from collections import defaultdict
from uuid import UUID as UUIDType

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import connection, models
from django.db.models import QuerySet
from django.db.models.expressions import RawSQL
from django.db.models.functions import Now
from django.db.models.query_utils import Q
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("email must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    objects = CustomUserManager()

    username = None
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.EmailField(unique=True)
    attributes = models.JSONField(null=False, default=dict)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def category_dict(self) -> dict[UUIDType | None, list["Feed"]]:
        category_dict = getattr(self, "_category_dict", None)
        if category_dict is None:
            category_dict = defaultdict(list)

            subscribed_feeds: list["Feed"] = []

            for m in User.subscribed_feeds.through.objects.filter(
                user=self
            ).select_related("feed"):
                feed = m.feed
                feed.custom_title = m.custom_feed_title
                subscribed_feeds.append(feed)

            for user_category in self.user_categories.all():
                feed_uuids = frozenset(
                    user_category.feeds.values_list("uuid", flat=True)
                )

                for subscribed_feed in subscribed_feeds:
                    if subscribed_feed.uuid in feed_uuids:
                        category_dict[user_category.uuid].append(subscribed_feed)
                    else:
                        category_dict[None].append(subscribed_feed)

            self._category_dict = category_dict

        return category_dict


class VerificationToken(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    expires_at = models.DateTimeField()
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_token",
    )

    @property
    def token_str(self):
        return str(self.uuid)

    @staticmethod
    def find_by_token(token: str):
        uuid_: uuid.UUID
        try:
            uuid_ = uuid.UUID(token)
        except (ValueError, TypeError):
            return None

        try:
            return VerificationToken.objects.get(uuid=uuid_, expires_at__gt=Now())
        except VerificationToken.DoesNotExist:
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
    subscribed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="subscribed_feeds",
        through="SubscribedFeedUserMapping",
    )

    @staticmethod
    def annotate_search_vectors(qs: QuerySet["Feed"]):
        if connection.vendor == "postgresql":  # pragma: no cover
            from django.contrib.postgres.search import SearchVectorField

            qs = qs.annotate(
                title_search_vector=RawSQL(
                    "title_search_vector", [], output_field=SearchVectorField()
                )
            )

        return qs

    @staticmethod
    def annotate_subscription_data(qs: QuerySet["Feed"], user: User):
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
        read_count = user.read_feed_entries.filter(feed=feed).count()
        unread_count = total_feed_entry_count - read_count

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


class SubscribedFeedUserMapping(models.Model):
    class Meta:
        unique_together = (("user", "feed"), ("user", "custom_feed_title"))

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    custom_feed_title = models.TextField(null=True)


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
    users_who_read = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="read_feed_entries",
        through="ReadFeedEntryUserMapping",
    )
    users_who_favorited = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="favorite_feed_entries"
    )

    @staticmethod
    def annotate_search_vectors(qs: QuerySet["FeedEntry"]):
        if connection.vendor == "postgresql":  # pragma: no cover
            from django.contrib.postgres.search import SearchVectorField

            qs = qs.annotate(
                title_search_vector=RawSQL(
                    "title_search_vector", [], output_field=SearchVectorField()
                ),
                content_search_vector=RawSQL(
                    "content_search_vector", [], output_field=SearchVectorField()
                ),
            )

        return qs


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
