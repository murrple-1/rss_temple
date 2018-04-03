import uuid

from django.db import models


class User(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.CharField(max_length=64, unique=True)

    def subscribed_channels(self):
        if not hasattr(self, '_subscribed_channels'):
            self._subscribed_channels = Channel.objects.filter(uuid__in=ChannelUserMapping.objects.filter(user=self).values('channel_id'))

        return self._subscribed_channels


class Login(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class MyLogin(Login):
    pw_hash = models.CharField(max_length=96)


class FacebookLogin(Login):
    pass


class Session(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    expires_at = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class Channel(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    feed_link = models.TextField(unique=True)
    title = models.TextField()
    home_link = models.TextField()
    description = models.TextField()


class ChannelUserMapping(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)


class ChannelItem(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    title = models.TextField()
    link = models.TextField()
    author = models.TextField()
