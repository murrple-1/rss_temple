import uuid

from django.db import models, connection
from django.utils import timezone
from django.db.models.functions import Now
from django.db.models.query_utils import Q
from django.db.models.expressions import RawSQL


class User(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    attributes = models.JSONField(null=False, default=dict)

    def category_dict(self):
        category_dict = getattr(self, '_category_dict', None)
        if category_dict is None:
            category_dict = {}

            for subscribed_feed_user_mapping in SubscribedFeedUserMapping.objects.select_related('feed').filter(user=self):
                feed_user_category_mappings = list(FeedUserCategoryMapping.objects.select_related(
                    'user_category').filter(feed=subscribed_feed_user_mapping.feed))

                keys = None
                if len(feed_user_category_mappings) > 0:
                    keys = frozenset(
                        feed_user_category_mapping.user_category.uuid for feed_user_category_mapping in feed_user_category_mappings)
                else:
                    keys = [None]

                feed = subscribed_feed_user_mapping.feed

                feed.custom_title = subscribed_feed_user_mapping.custom_feed_title

                for key in keys:
                    if key not in category_dict:
                        category_dict[key] = []

                    category_dict[key].append(feed)

            self._category_dict = category_dict

        return category_dict

    def subscribed_feeds_dict(self):
        subscribed_feeds_dict = getattr(self, '_subscribed_feeds_dict', None)
        if subscribed_feeds_dict is None:
            subscribed_feeds_dict = dict((mapping.feed.uuid, mapping.feed)
                                         for mapping in SubscribedFeedUserMapping.objects.select_related('feed').filter(user=self))
            self._subscribed_feeds_dict = subscribed_feeds_dict

        return subscribed_feeds_dict

    def read_feed_entry_mappings(self):
        read_feed_entry_mappings = getattr(
            self, '_read_feed_entry_mappings', None)
        if read_feed_entry_mappings is None:
            read_feed_entry_mappings = ReadFeedEntryUserMapping.objects.filter(
                user=self)
            self._read_feed_entry_mappings = read_feed_entry_mappings

        return read_feed_entry_mappings

    def read_feed_entry_uuids(self):
        read_feed_entry_uuids = getattr(self, '_read_feed_entry_uuids', None)
        if read_feed_entry_uuids is None:
            read_feed_entry_uuids = frozenset(
                _uuid for _uuid in self.read_feed_entry_mappings().values_list('feed_entry_id', flat=True))
            self._read_feed_entry_uuids = read_feed_entry_uuids

        return read_feed_entry_uuids

    def favorite_feed_entry_mappings(self):
        favorite_feed_entry_mappings = getattr(
            self, '_favorite_feed_entry_mappings', None)
        if favorite_feed_entry_mappings is None:
            favorite_feed_entry_mappings = FavoriteFeedEntryUserMapping.objects.filter(
                user=self)
            self._favorite_feed_entry_mappings = favorite_feed_entry_mappings

        return favorite_feed_entry_mappings

    def favorite_feed_entry_uuids(self):
        favorite_feed_entry_uuids = getattr(
            self, '_favorite_feed_entry_uuids', None)
        if favorite_feed_entry_uuids is None:
            favorite_feed_entry_uuids = frozenset(
                _uuid for _uuid in self.favorite_feed_entry_mappings().values_list('feed_entry_id', flat=True))
            self._favorite_feed_entry_uuids = favorite_feed_entry_uuids

        return favorite_feed_entry_uuids

    def my_login(self):
        if not hasattr(self, '_my_login'):
            try:
                self._my_login = MyLogin.objects.get(user=self)
            except MyLogin.DoesNotExist:
                self._my_login = None

        return self._my_login

    def google_login(self):
        if not hasattr(self, '_google_login'):
            try:
                self._google_login = GoogleLogin.objects.get(user=self)
            except GoogleLogin.DoesNotExist:
                self._google_login = None

        return self._google_login

    def facebook_login(self):
        if not hasattr(self, '_facebook_login'):
            try:
                self._facebook_login = FacebookLogin.objects.get(user=self)
            except FacebookLogin.DoesNotExist:
                self._facebook_login = None

        return self._facebook_login


class Login(models.Model):
    class Meta:
        abstract = True

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.OneToOneField(User, on_delete=models.CASCADE)


class MyLogin(Login):
    pw_hash = models.CharField(max_length=96)


class GoogleLogin(Login):
    g_user_id = models.CharField(max_length=96)


class FacebookLogin(Login):
    profile_id = models.CharField(max_length=96)


class Session(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    expires_at = models.DateTimeField(null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class VerificationToken(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    expires_at = models.DateTimeField()
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def token_str(self):
        return str(self.uuid)

    @staticmethod
    def find_by_token(token):
        _uuid = None
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
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def token_str(self):
        return str(self.uuid)

    @staticmethod
    def find_by_token(token):
        _uuid = None
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
        unique_together = (('user', 'text'),)

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()

    def feeds(self):
        feeds = getattr(self, '_feeds', None)
        if feeds is None:
            feeds = Feed.objects.filter(
                uuid__in=FeedUserCategoryMapping.objects.filter(user_category=self).values_list('feed_id', flat=True))
            self._feeds = feeds

        return feeds


class Feed(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['update_backoff_until']),
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
    def annotate_search_vectors(qs):
        if connection.vendor == 'postgresql':
            from django.contrib.postgres.search import SearchVectorField
            qs = qs.annotate(title_search_vector=RawSQL(
                'title_search_vector', [], output_field=SearchVectorField()))

        return qs

    @staticmethod
    def annotate_subscription_data(qs, user):
        subscribed_user_feed_mappings = SubscribedFeedUserMapping.objects.filter(
            user=user, feed_id=models.OuterRef('uuid'))
        return qs.annotate(
            custom_title=models.Subquery(
                subscribed_user_feed_mappings.values('custom_feed_title')),
            is_subscribed=models.Exists(subscribed_user_feed_mappings),
        )

    def with_subscription_data(self):
        self.custom_title = None
        self.is_subscribed = False

    def user_categories(self, user):
        if not hasattr(self, '_user_categories'):
            category_dict = user.category_dict()

            user_category_uuids = set()

            for uuid_, feeds in category_dict.items():
                feed_uuids = frozenset(feed.uuid for feed in feeds)

                if self.uuid in feed_uuids:
                    user_category_uuids.add(uuid_)

            self._user_categories = UserCategory.objects.filter(
                uuid__in=user_category_uuids)

        return self._user_categories

    def feed_entries(self):
        feed_entries = getattr(self, '_feed_entries', None)
        if feed_entries is None:
            feed_entries = FeedEntry.objects.filter(feed=self)
            self._feed_entries = feed_entries

        return feed_entries

    @staticmethod
    def _generate_counts(feed, user):
        total_feed_entry_count = feed.feed_entries().count()
        read_count = ReadFeedEntryUserMapping.objects.filter(
            feed_entry__feed=feed, user=user).count()
        unread_count = total_feed_entry_count - read_count

        counts = {
            'unread_count': unread_count,
            'read_count': read_count,
        }

        return counts

    def _counts(self, user):
        counts = getattr(self, '_counts_', None)
        if counts is None:
            counts = Feed._generate_counts(self, user)
            self._counts_ = counts

        return counts

    def unread_count(self, user):
        return self._counts(user)['unread_count']

    def read_count(self, user):
        return self._counts(user)['read_count']


class SubscribedFeedUserMapping(models.Model):
    class Meta:
        unique_together = (('user', 'feed'), ('user', 'custom_feed_title'))

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    custom_feed_title = models.TextField(null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class FeedUserCategoryMapping(models.Model):
    class Meta:
        unique_together = (('feed', 'user_category'),)

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    user_category = models.ForeignKey(
        UserCategory, on_delete=models.CASCADE)


class FeedEntry(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['id']),
            models.Index(fields=['url']),
        ]

        constraints = [
            models.UniqueConstraint(fields=[
                                    'feed', 'url'], name='unique__feed__url__when__updated_at__null', condition=Q(updated_at__isnull=True)),
            models.UniqueConstraint(fields=[
                                    'feed', 'url', 'updated_at'], name='unique__feed__url__when__updated_at__not_null'),
        ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    id = models.TextField(null=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
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
        if connection.vendor == 'postgresql':
            from django.contrib.postgres.search import SearchVectorField
            qs = qs.annotate(title_search_vector=RawSQL('title_search_vector', [], output_field=SearchVectorField(
            )), content_search_vector=RawSQL('content_search_vector', [], output_field=SearchVectorField()))

        return qs

    def from_subscription(self, user):
        from_subscription = getattr(self, '_from_subscription', None)
        if from_subscription is None:
            from_subscription = self.feed_id in (
                f.uuid for f in user.subscribed_feeds_dict().values())
            self._from_subscription = from_subscription

        return from_subscription

    def is_read(self, user):
        is_read = getattr(self, '_is_read', None)
        if is_read is None:
            is_read = self.uuid in user.read_feed_entry_uuids()
            self._is_read = is_read

        return is_read

    def is_favorite(self, user):
        is_favorite = getattr(self, '_is_favorite', None)
        if is_favorite is None:
            is_favorite = self.uuid in user.favorite_feed_entry_uuids()
            self._is_favorite = is_favorite

        return is_favorite

    def read_mapping(self, user):
        if not hasattr(self, '_read_mapping'):
            self._read_mapping = next((rfe for rfe in user.read_feed_entry_mappings(
            ) if rfe.feed_entry_id == self.uuid), None)

        return self._read_mapping


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


class FeedSubscriptionProgressEntry(models.Model):
    NOT_STARTED = 0
    STARTED = 1
    FINISHED = 2

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.IntegerField(default=NOT_STARTED, choices=[(
        NOT_STARTED, 'Not Started'), (STARTED, 'Started'), (FINISHED, 'Finished')])


class FeedSubscriptionProgressEntryDescriptor(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed_subscription_progress_entry = models.ForeignKey(
        FeedSubscriptionProgressEntry, on_delete=models.CASCADE)
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
        (TYPE_TO, 'To'),
        (TYPE_CC, 'CC'),
        (TYPE_BCC, 'BCC'),
    )

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    type = models.IntegerField(choices=TYPE_CHOICES)
    email = models.CharField(max_length=256)
    entry = models.ForeignKey(NotifyEmailQueueEntry, on_delete=models.CASCADE)
