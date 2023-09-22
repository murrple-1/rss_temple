import datetime
import logging
import logging.handlers
import traceback
from typing import Any, Iterable

from bs4 import BeautifulSoup
from django.core.management.base import CommandError, CommandParser
from django.db.utils import OperationalError
from django.utils import timezone
from goose3 import Configuration, Goose, Image

from api.goose import default_config as default_goose3_config
from api.models import FeedEntry

from ._daemoncommand import DaemonCommand


class Command(DaemonCommand):
    help = "Daemon to find so-called 'top images' for entries without images"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--sleep-seconds", type=float, default=30.0)  # 30 seconds
        parser.add_argument("--single-run", action="store_true")
        parser.add_argument("--since")
        parser.add_argument("--loop-count", type=int, default=50)
        parser.add_argument("--image-min-bytes", type=int, default=20000)
        parser.add_argument("--goose-log-filepath", default="logs/goose3.log")
        parser.add_argument("--goose-log-stderr", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        goose3_logger = logging.getLogger("goose3")
        goose3_logger.addHandler(
            logging.handlers.RotatingFileHandler(
                filename=options["goose_log_filepath"], backupCount=5, maxBytes=100000
            )
        )
        if options["goose_log_stderr"]:
            goose3_logger.addHandler(logging.StreamHandler(self.stderr))

        verbosity = options["verbosity"]
        since = (
            datetime.datetime.fromisoformat(since_str)
            if (since_str := options["since"]) is not None
            else datetime.datetime.min
        )
        if timezone.is_naive(since):
            since = timezone.make_aware(since)

        goose3_config = default_goose3_config()
        goose3_config.enable_image_fetching = True
        goose3_config._known_author_patterns = []
        goose3_config._known_context_patterns = []
        goose3_config._known_publish_date_tags = []
        goose3_config.images_min_bytes = options["image_min_bytes"]
        goose3_config.strict = False

        if options["single_run"]:
            total_remaining = FeedEntry.objects.filter(
                has_top_image_been_processed=False
            ).count()

            count = self._find_top_images(
                FeedEntry.objects.filter(has_top_image_been_processed=False)
                .filter(published_at__gte=since)
                .order_by("-published_at")
                .iterator(),
                goose3_config,
                verbosity=verbosity,
            )
            self.stderr.write(f"updated {count}/{total_remaining}")
        else:
            exit = self._setup_exit_event()

            try:
                while not exit.is_set():
                    count = self._find_top_images(
                        FeedEntry.objects.filter(has_top_image_been_processed=False)
                        .filter(published_at__gte=since)
                        .order_by("-published_at")[: options["loop_count"]],
                        goose3_config,
                        verbosity=verbosity,
                    )
                    if verbosity >= 2:
                        self.stderr.write(self.style.NOTICE(f"updated {count}"))

                    exit.wait(options["sleep_seconds"])
            except OperationalError as e:
                raise CommandError("db went away") from e
            except Exception as e:
                raise CommandError("loop stopped unexpectedly") from e

    def _find_top_images(
        self,
        feed_entry_queryset: Iterable[FeedEntry],
        goose3_config: Configuration,
        verbosity=1,
    ) -> int:
        count = 0
        with Goose(goose3_config) as g:
            for feed_entry in feed_entry_queryset:
                soup = BeautifulSoup(feed_entry.content, "lxml")
                if len(soup.findAll("img")) < 1:
                    try:
                        article = g.extract(url=feed_entry.url)
                        top_image: Image | None = article.top_image
                        if top_image is not None:
                            feed_entry.top_image_src = top_image.src
                        else:
                            feed_entry.top_image_src = ""
                    except Exception:
                        if verbosity >= 2:
                            self.stderr.write(
                                self.style.ERROR(
                                    f"failed to scrap feed '{feed_entry.url}'\n{traceback.format_exc()}"
                                )
                            )

                        feed_entry.top_image_src = ""
                else:
                    feed_entry.top_image_src = ""

                feed_entry.has_top_image_been_processed = True
                feed_entry.save(
                    update_fields=("has_top_image_been_processed", "top_image_src")
                )

                count += 1
        return count
