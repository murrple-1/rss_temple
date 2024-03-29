from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django_apscheduler import util
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution

from api_dramatiq.broker import broker
from api_dramatiq.encoder import UJSONEncoder


@util.close_old_connections
def _delete_old_job_executions(max_age=604_800):
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


def _archive_feed_entries(
    *args: Any, options: dict[str, Any] | None = None, **kwargs: Any
):
    from dramatiq import Message

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
    from dramatiq import Message

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
    from dramatiq import Message

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
    from dramatiq import Message

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
    from dramatiq import Message

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
    from dramatiq import Message

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
    from dramatiq import Message

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


def _flag_duplicate_feeds(
    *args: Any, options: dict[str, Any] | None = None, **kwargs: Any
):
    from dramatiq import Message

    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="flag_duplicate_feeds",
            args=args,
            kwargs=kwargs,
            options=options,
        )
    )


def _purge_duplicate_feed_urls(
    *args: Any, options: dict[str, Any] | None = None, **kwargs: Any
):
    from dramatiq import Message

    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="purge_duplicate_feed_urls",
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
        parser.add_argument("--archive-feed-entries-limit", type=int, default=1000)

        parser.add_argument(
            "--extract-top-images-crontab", default="0 * * * *"
        )  # every hour, on the first minute
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
        parser.add_argument(
            "--extract-top-images-response-max-byte-count",
            type=int,
            default=-1,
        )
        parser.add_argument("--extract-top-images-db-limit", type=int, default=50)
        parser.add_argument("--extract-top-images-since")

        parser.add_argument(
            "--label-feeds-crontab", default="0 0 * * *"
        )  # every midnight
        parser.add_argument("--label-feeds-top-x", type=int, default=3)

        parser.add_argument(
            "--label-users-crontab", default="0 0 * * *"
        )  # every midnight
        parser.add_argument("--label-users-top-x", type=int, default=3)

        parser.add_argument("--feed-scrape-interval-seconds", type=int, default=30)
        parser.add_argument(
            "--feed-scrape-max-age", type=int, default=(1000 * 25)
        )  # 25 seconds
        parser.add_argument(
            "--feed-scrape-response-max-byte-count", type=int, default=-1
        )
        parser.add_argument("--feed-scrape-db-limit", type=int, default=1000)
        parser.add_argument(
            "--feed-scrape-is-dead-max-interval-seconds",
            type=float,
            default=settings.FEED_IS_DEAD_MAX_INTERVAL.total_seconds(),
        )
        parser.add_argument(
            "--feed-scrape-should-scrape-dead-feeds", action="store_true"
        )

        parser.add_argument(
            "--setup-subscriptions-interval-seconds", type=int, default=30
        )
        parser.add_argument(
            "--setup-subscriptions-max-age", type=int, default=(1000 * 25)
        )  # 25 seconds
        parser.add_argument(
            "--setup-subscriptions-response-max-byte-count",
            type=int,
            default=-1,
        )

        parser.add_argument(
            "--purge-expired-data-crontab", default="0 0 */15 * *"
        )  # every 1st and 15th, at midnight

        parser.add_argument(
            "--flag-duplicate-feeds-crontab", default="0 0 * * *"
        )  # every midnight
        parser.add_argument("--flag-duplicate-feeds-feed-count", type=int, default=1000)
        parser.add_argument(
            "--flag-duplicate-feeds-entry-compare-count", type=int, default=50
        )
        parser.add_argument(
            "--flag-duplicate-feeds-entry-intersection-threshold", type=int, default=5
        )

        parser.add_argument(
            "--purge-duplicate-feed-urls-crontab", default="0 0 */15 * *"
        )  # every 1st and 15th, at midnight

    def handle(self, *args: Any, **options: Any) -> None:
        import dramatiq

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
            args=(options["extract_top_images_response_max_byte_count"],),
            kwargs={
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
        )
        scheduler.add_job(
            _feed_scrape,
            trigger=IntervalTrigger(seconds=options["feed_scrape_interval_seconds"]),
            id="feed_scrape",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            args=(
                options["feed_scrape_response_max_byte_count"],
                options["feed_scrape_should_scrape_dead_feeds"],
            ),
            kwargs={
                "options": {
                    "max_age": options["feed_scrape_max_age"],
                },
                "db_limit": options["feed_scrape_db_limit"],
                "is_dead_max_interval_seconds": options[
                    "feed_scrape_is_dead_max_interval_seconds"
                ],
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
            args=(options["setup_subscriptions_response_max_byte_count"],),
            kwargs={
                "options": {
                    "max_age": options["setup_subscriptions_max_age"],
                },
            },
        )
        scheduler.add_job(
            _flag_duplicate_feeds,
            trigger=CronTrigger.from_crontab(options["flag_duplicate_feeds_crontab"]),
            id="flag_duplicate_feeds",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "feed_count": options["flag_duplicate_feeds_feed_count"],
                "entry_compare_count": options[
                    "flag_duplicate_feeds_entry_compare_count"
                ],
                "entry_intersection_threshold": options[
                    "flag_duplicate_feeds_entry_intersection_threshold"
                ],
            },
        )
        scheduler.add_job(
            _purge_duplicate_feed_urls,
            trigger=CronTrigger.from_crontab(
                options["purge_duplicate_feed_urls_crontab"]
            ),
            id="purge_duplicate_feed_urls",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
        )

        try:
            self.stderr.write(self.style.NOTICE("Starting scheduler..."))
            scheduler.start()
        except KeyboardInterrupt:
            self.stderr.write(self.style.NOTICE("Stopping scheduler..."))
            scheduler.shutdown()
