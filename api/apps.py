import dramatiq
from django.apps import AppConfig
from django.conf import settings

from api_dramatiq.broker import broker
from api_dramatiq.encoder import UJSONEncoder


class ApiConfig(AppConfig):
    name = "api"

    def ready(self) -> None:
        super().ready()

        # `api.signals` only holds django-silk handlers, and importing `silk.models` fails when silk isn't in INSTALLED_APPS
        if settings.SILK_ENABLED:
            import api.signals

            assert api.signals

        dramatiq.set_broker(broker)
        dramatiq.set_encoder(UJSONEncoder())
