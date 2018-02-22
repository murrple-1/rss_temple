import uuid

from django.db import models

class User(models.Model):
	uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
	email = models.CharField(max_length=64)
	pw_hash = models.CharField(max_length=96)

class Session(models.Model):
	uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)

class RssEntry(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
