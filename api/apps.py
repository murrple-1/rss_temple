import dramatiq
from django.apps import AppConfig

from api_dramatiq.broker import broker
from api_dramatiq.encoder import UJSONEncoder


class ApiConfig(AppConfig):
    name = "api"

    def ready(self) -> None:
        import api.signals

        assert api.signals

        super().ready()

        dramatiq.set_broker(broker)
        dramatiq.set_encoder(UJSONEncoder())
