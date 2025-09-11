import dramatiq
from django.apps import AppConfig


from api_dramatiq.broker import broker
from api_dramatiq.encoder import UJSONEncoder


class ApiConfig(AppConfig):
    name = "api"

    def ready(self) -> None:
        super().ready()

        import api.signals

        assert api.signals

        dramatiq.set_broker(broker)
        dramatiq.set_encoder(UJSONEncoder())

        from api.pg_ts_config import load_pg_ts_configs

        load_pg_ts_configs()
