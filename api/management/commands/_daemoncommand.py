import signal
from threading import Event
from types import FrameType

from django.core.management.base import BaseCommand


class DaemonCommand(BaseCommand):
    def _setup_exit_event(self):  # pragma: no cover
        exit = Event()

        def _quit(signo: int, frame: FrameType | None):
            exit.set()

        signal.signal(signal.SIGTERM, _quit)

        return exit
