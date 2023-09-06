from typing import Any

from django.core.management.base import CommandError, CommandParser
from django.db import transaction
from django.db.models.functions import Now
from django.db.utils import OperationalError

from api.models import Captcha

from ._daemoncommand import DaemonCommand


class Command(DaemonCommand):
    help = "Daemon to periodically purge expired data"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument(
            "--sleep-seconds", type=float, default=60.0 * 60.0 * 24.0
        )  # 24 hours
        parser.add_argument("--single-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        if options["single_run"]:
            msgs = self._purge()
            self.stderr.write(self.style.NOTICE("\n".join(msgs)))
        else:
            exit = self._setup_exit_event()

            try:
                while not exit.is_set():
                    msgs = self._purge()
                    self.stderr.write(self.style.NOTICE("\n".join(msgs)))

                    exit.wait(options["sleep_seconds"])
            except OperationalError as e:
                raise CommandError("db went away") from e
            except Exception as e:
                raise CommandError("loop stopped unexpectedly") from e

    def _purge(self) -> list[str]:
        msgs: list[str] = []
        with transaction.atomic():
            _, deletes = Captcha.objects.filter(expires_at__lte=Now()).delete()
            captcha_count = deletes.get("api.Captcha", 0)
            msgs.append(f"removed {captcha_count} captchas")

        return msgs
