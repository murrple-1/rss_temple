from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = "api"

    def ready(self) -> None:
        from api.deferredattribute_monkey_patch import monkey_patch

        monkey_patch()

        return super().ready()
