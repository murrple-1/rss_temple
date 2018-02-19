from django.db import models


class RssEntry(models.Model):
    uuid = models.UUIDField(primary_key=True)
