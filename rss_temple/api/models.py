import uuid

from django.db import models

class User(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.CharField(max_length=64, unique=True)

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
    title = models.TextField()
    link = models.TextField()
    description = models.TextField()
