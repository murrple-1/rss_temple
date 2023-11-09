from typing import Any

import dramatiq
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django_apscheduler import util
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from dramatiq import Message

from api_dramatiq.broker import broker
from api_dramatiq.encoder import UJSONEncoder


@util.close_old_connections
def _delete_old_job_executions(max_age=604_800):
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


def _archive_feed_entries(
    *args: Any, options: dict[str, Any] | None = None, **kwargs: Any
):
    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="archive_feed_entries",
            args=args,
            kwargs=kwargs,
            options=options,
        )
    )


def _extract_top_images(
    *args: Any, options: dict[str, Any] | None = None, **kwargs: Any
):
    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="extract_top_images",
            args=args,
            kwargs=kwargs,
            options=options,
        )
    )


def _label_feeds(*args: Any, options: dict[str, Any] | None = None, **kwargs: Any):
    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="label_feeds",
            args=args,
            kwargs=kwargs,
            options=options,
        )
    )


def _label_users(*args: Any, options: dict[str, Any] | None = None, **kwargs: Any):
    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="label_users",
            args=args,
            kwargs=kwargs,
            options=options,
        )
    )


def _purge_expired_data(
    *args: Any, options: dict[str, Any] | None = None, **kwargs: Any
):
    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="purge_expired_data",
            args=args,
            kwargs=kwargs,
            options=options,
        )
    )


def _feed_scrape(*args: Any, options: dict[str, Any] | None = None, **kwargs: Any):
    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="feed_scrape",
            args=args,
            kwargs=kwargs,
            options=options,
        )
    )


def _setup_subscriptions(
    *args: Any, options: dict[str, Any] | None = None, **kwargs: Any
):
    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="setup_subscriptions",
            args=args,
            kwargs=kwargs,
            options=options,
        )
    )


class Command(BaseCommand):
    help = "Run the tasks on a schedule"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--delete-old-job-executions-crontab", default="0 0 * * 0"
        )  # every Sunday at midnight

        parser.add_argument(
            "--archive-feed-entries-crontab", default="*/30 * * * *"
        )  # every half-hour, on the half-hour
        parser.add_argument(
            "--archive-feed-entries-max-age",
            type=int,
            default=(1000 * 60 * 25),  # 25 minutes
        )
        parser.add_argument("--archive-feed-entries-limit", type=int, default=1000)

        parser.add_argument(
            "--extract-top-images-crontab", default="0 * * * *"
        )  # every hour, on the first minute
        parser.add_argument(
            "--extract-top-images-max-age",
            type=int,
            default=(1000 * 60 * 55),  # 55 minutes
        )
        parser.add_argument(
            "--extract-top-images-max-processing-attempts", type=int, default=3
        )
        parser.add_argument(
            "--extract-top-images-min-image-byte-count", type=int, default=4500
        )
        parser.add_argument(
            "--extract-top-images-min-image-width", type=int, default=250
        )
        parser.add_argument(
            "--extract-top-images-min-image-height", type=int, default=250
        )
        parser.add_argument("--extract-top-images-db-limit", type=int, default=50)
        parser.add_argument("--extract-top-images-since")

        parser.add_argument(
            "--label-feeds-crontab", default="0 0 * * *"
        )  # every midnight
        parser.add_argument(
            "--label-feeds-max-age", type=int, default=(1000 * 60 * 60 * 23)
        )  # 23 hours
        parser.add_argument("--label-feeds-top-x", type=int, default=3)

        parser.add_argument(
            "--label-users-crontab", default="0 0 * * *"
        )  # every midnight
        parser.add_argument(
            "--label-users-max-age", type=int, default=(1000 * 60 * 60 * 23)
        )  # 23 hours
        parser.add_argument("--label-users-top-x", type=int, default=3)

        parser.add_argument("--feed-scrape-interval-seconds", type=int, default=30)
        parser.add_argument(
            "--feed-scrape-max-age", type=int, default=(1000 * 25)
        )  # 25 seconds
        parser.add_argument("--feed-scrape-db-limit", type=int, default=1000)

        parser.add_argument(
            "--setup-subscriptions-interval-seconds", type=int, default=30
        )
        parser.add_argument(
            "--setup-subscriptions-max-age", type=int, default=(1000 * 25)
        )  # 25 seconds

        parser.add_argument(
            "--purge-expired-data-crontab", default="0 0 */15 * *"
        )  # every 1st and 15th, at midnight
        parser.add_argument(
            "--purge-expired-data-max-age", type=int, default=(1000 * 60 * 60 * 24 * 14)
        )  # 14 days

    def handle(self, *args: Any, **options: Any) -> None:
        dramatiq.set_encoder(UJSONEncoder())

        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        scheduler.add_job(
            _delete_old_job_executions,
            trigger=CronTrigger.from_crontab(
                options["delete_old_job_executions_crontab"]
            ),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
        )

        scheduler.add_job(
            _archive_feed_entries,
            trigger=CronTrigger.from_crontab(options["archive_feed_entries_crontab"]),
            id="archive_feed_entries",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "options": {
                    "max_age": options["archive_feed_entries_max_age"],
                },
                "limit": options["archive_feed_entries_limit"],
            },
        )
        scheduler.add_job(
            _extract_top_images,
            trigger=CronTrigger.from_crontab(options["extract_top_images_crontab"]),
            id="extract_top_images",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "options": {
                    "max_age": options["extract_top_images_max_age"],
                },
                "max_processing_attempts": options[
                    "extract_top_images_max_processing_attempts"
                ],
                "min_image_byte_count": options[
                    "extract_top_images_min_image_byte_count"
                ],
                "min_image_width": options["extract_top_images_min_image_width"],
                "min_image_height": options["extract_top_images_min_image_height"],
                "db_limit": options["extract_top_images_db_limit"],
                "since": options["extract_top_images_since"],
            },
        )
        scheduler.add_job(
            _label_feeds,
            trigger=CronTrigger.from_crontab(options["label_feeds_crontab"]),
            id="label_feeds",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "options": {
                    "max_age": options["label_feeds_max_age"],
                },
                "top_x": options["label_feeds_top_x"],
            },
        )
        scheduler.add_job(
            _label_users,
            trigger=CronTrigger.from_crontab(options["label_users_crontab"]),
            id="label_users",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "options": {
                    "max_age": options["label_users_max_age"],
                },
                "top_x": options["label_users_top_x"],
            },
        )
        scheduler.add_job(
            _purge_expired_data,
            trigger=CronTrigger.from_crontab(options["purge_expired_data_crontab"]),
            id="purge_expired_data",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "options": {
                    "max_age": options["purge_expired_data_max_age"],
                },
            },
        )
        scheduler.add_job(
            _feed_scrape,
            trigger=IntervalTrigger(seconds=options["feed_scrape_interval_seconds"]),
            id="feed_scrape",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "options": {
                    "max_age": options["feed_scrape_max_age"],
                },
                "db_limit": options["feed_scrape_db_limit"],
            },
        )
        scheduler.add_job(
            _setup_subscriptions,
            trigger=IntervalTrigger(
                seconds=options["setup_subscriptions_interval_seconds"]
            ),
            id="setup_subscriptions",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "options": {
                    "max_age": options["setup_subscriptions_max_age"],
                }
            },
        )

        try:
            self.stderr.write(self.style.NOTICE("Starting scheduler..."))
            scheduler.start()
        except KeyboardInterrupt:
            self.stderr.write(self.style.NOTICE("Stopping scheduler..."))
            scheduler.shutdown()
