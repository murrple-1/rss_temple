import os

from django.conf import settings
from django.db import models
from django.dispatch import receiver

# `silk.models` can only be imported when silk is in INSTALLED_APPS (see `APP_ENABLE_SILK`)
if settings.SILK_ENABLED:
    from silk.models import Request

    @receiver(models.signals.post_delete, sender=Request)
    def auto_delete_request_prof_file_on_delete(
        sender, instance, **kwargs
    ):  # pragma: no cover
        assert isinstance(instance, Request)

        if instance.prof_file:
            if os.path.isfile(instance.prof_file.path):
                os.remove(instance.prof_file.path)
