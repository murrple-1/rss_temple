from typing import Any

import ujson
from apscheduler.schedulers.blocking import BlockingScheduler
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django_apscheduler.jobstores import DjangoJobStore
from rest_framework import serializers as serializers_

from api.management.commands import _schedulerdaemon_serializers as serializers
from api_dramatiq.encoder import UJSONEncoder


class Command(BaseCommand):
    help = "Run the tasks on a schedule"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("setup_json_filepath")

    def handle(self, *args: Any, **options: Any) -> None:
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        setup_dict: Any
        with open(options["setup_json_filepath"], "r") as f:
            setup_dict = ujson.load(f)

        serializer = serializers.SetupSerializer(
            data=setup_dict, context={"scheduler": scheduler}
        )
        try:
            serializer.is_valid(raise_exception=True)
        except serializers_.ValidationError as e:
            raise CommandError(e)

        serializer.save()

        import dramatiq

        dramatiq.set_encoder(UJSONEncoder())

        try:
            self.stderr.write(self.style.NOTICE("Starting scheduler..."))
            scheduler.start()
        except KeyboardInterrupt:
            self.stderr.write(self.style.NOTICE("Stopping scheduler..."))
            scheduler.shutdown()
