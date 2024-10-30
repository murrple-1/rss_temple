import os

from django.db import models
from django.dispatch import receiver
from silk.models import Request


@receiver(models.signals.post_delete, sender=Request)
def auto_delete_request_prof_file_on_delete(
    sender, instance, **kwargs
):  # pragma: no cover
    assert isinstance(instance, Request)

    if instance.prof_file:
        if os.path.isfile(instance.prof_file.path):
            os.remove(instance.prof_file.path)
