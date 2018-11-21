import uuid

from django.db import models
from django.utils import timezone


class User(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.CharField(max_length=64, unique=True)

    def category_dict(self):
        if not hasattr(self, '_category_dict'):
            subcribed_feed_user_mappings = SubscribedFeedUserMapping.objects.select_related(
                'feed', 'user_category').filter(user=self)

            category_dict = {}

            for subcribed_feed_user_mapping in subcribed_feed_user_mappings:
                key = subcribed_feed_user_mapping.user_category.text if subcribed_feed_user_mapping.user_category is not None else None

                if key not in category_dict:
                    category_dict[key] = []

                feed = subcribed_feed_user_mapping.feed

                feed._custom_title = subcribed_feed_user_mapping.custom_feed_title

                category_dict[key].append(feed)

            self._category_dict = category_dict

        return self._category_dict

    def subscribed_feeds(self):
        if not hasattr(self, '_subscribed_feeds'):
            feeds = []

            for _feeds in self.category_dict().values():
                feeds.extend(_feeds)

            self._subscribed_feeds = feeds

        return self._subscribed_feeds

    def read_feed_entries(self):
        if not hasattr(self, '_read_feed_entries'):
            self._read_feed_entries = FeedEntry.objects.filter(
                uuid__in=ReadFeedEntryUserMapping.objects.filter(user=self).values('feed_entry_id'))

        return self._read_feed_entries

    def read_feed_entry_uuids(self):
        if not hasattr(self, '_read_feed_entry_uuids'):
            self._read_feed_entry_uuids = frozenset(
                _uuid for _uuid in self.read_feed_entries().values_list('uuid', flat=True))

        return self._read_feed_entry_uuids

    def favorite_feed_entries(self):
        if not hasattr(self, '_favorite_feed_entries'):
            self._favorite_feed_entries = FeedEntry.objects.filter(
                uuid__in=FavoriteFeedEntryUserMapping.objects.filter(user=self).values('feed_entry_id'))

        return self._favorite_feed_entries

    def favorite_feed_entry_uuids(self):
        if not hasattr(self, '_favorite_feed_entry_uuids'):
            self._favorite_feed_entry_uuids = frozenset(
                _uuid for _uuid in self.favorite_feed_entries().values_list('uuid', flat=True))

        return self._favorite_feed_entry_uuids


class Login(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class MyLogin(Login):
    pw_hash = models.CharField(max_length=96)


class FacebookLogin(Login):
    profile_id = models.CharField(max_length=96)


class GoogleLogin(Login):
    g_user_id = models.CharField(max_length=96)


class Session(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    expires_at = models.DateTimeField(null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class UserCategory(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(unique=True)


class Feed(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed_url = models.TextField(unique=True)
    title = models.TextField(null=True)
    home_url = models.TextField(null=True)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True)
    db_created_at = models.DateTimeField(default=timezone.now)
    db_updated_at = models.DateTimeField(null=True)

    def subscribed(self, user):
        if not hasattr(self, '_subscribed'):
            self._subscribed = self.uuid in (
                feed.uuid for feed in user.subscribed_feeds())

        return self._subscribed

    def custom_title(self, user):
        if not hasattr(self, '_custom_title'):
            subscribed_feed = next(
                (feed for feed in user.subscribed_feeds() if feed.uuid == self.uuid), None)

            self._custom_title = subscribed_feed._custom_title if subscribed_feed is not None else None

        return self._custom_title


class SubscribedFeedUserMapping(models.Model):
    class Meta:
        unique_together = (('user', 'feed'), ('user', 'custom_feed_title'))

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    custom_feed_title = models.TextField(null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_category = models.ForeignKey(
        UserCategory, null=True, on_delete=models.SET_NULL)


class FeedEntry(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['id']),
        ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    id = models.TextField(null=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    created_at = models.DateTimeField(null=True)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True)
    title = models.TextField(null=True)
    url = models.TextField(null=True)
    content = models.TextField(null=True)
    author_name = models.TextField(null=True)
    hash = models.IntegerField()
    db_created_at = models.DateTimeField(default=timezone.now)
    db_updated_at = models.DateTimeField(null=True)

    def __eq__(self, other):
        if isinstance(other, FeedEntry):
            return (
                self.id == other.id
                and self.created_at == other.created_at
                and self.published_at == other.published_at
                and self.updated_at == other.updated_at
                and self.title == other.title
                and self.url == other.url
                and self.content == other.content
                and self.author_name == other.author_name
            )
        else:
            return False

    def __hash__(self):
        return hash((self.id, self.created_at, self.published_at, self.updated_at, self.title, self.url, self.content, self.author_name))

    def from_subscription(self, user):
        if not hasattr(self, '_from_subscription'):
            self._from_subscription = self.feed_id in (
                f.uuid for f in user.subscribed_feeds())

        return self._from_subscription

    def is_read(self, user):
        if not hasattr(self, '_is_read'):
            self._is_read = self.uuid in user.read_feed_entry_uuids()

        return self._is_read

    def is_favorite(self, user):
        if not hasattr(self, '_is_favorite'):
            self._is_favorite = self.uuid in user.favorite_feed_entry_uuids()

        return self._is_favorite


class Tag(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    label_text = models.TextField(unique=True)


class FeedTagMapping(models.Model):
    class Meta:
        unique_together = (('feed', 'tag'),)

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)


class FeedEntryTagMapping(models.Model):
    class Meta:
        unique_together = (('feed_entry', 'tag'),)

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed_entry = models.ForeignKey(FeedEntry, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)


class ReadFeedEntryUserMapping(models.Model):
    class Meta:
        unique_together = (('feed_entry', 'user'))

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed_entry = models.ForeignKey(FeedEntry, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(default=timezone.now)


class FavoriteFeedEntryUserMapping(models.Model):
    class Meta:
        unique_together = (('feed_entry', 'user'))

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed_entry = models.ForeignKey(FeedEntry, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
