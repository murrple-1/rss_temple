import uuid

from django.db import models
from django.utils import timezone

class User(models.Model):
	uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
	email = models.CharField(max_length=64, unique=True)
	pw_hash = models.CharField(max_length=96)

class Session(models.Model):
	uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
	expires_at = models.DateTimeField(default=timezone.now)

class RssEntry(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
