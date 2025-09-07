from typing import Any

from django_apscheduler import util
from django_apscheduler.models import DjangoJobExecution

from api_dramatiq.broker import broker


@util.close_old_connections
def delete_old_job_executions(max_age: int | None = None):
    if max_age is None:
        max_age = 604800

    DjangoJobExecution.objects.delete_old_job_executions(max_age)


def archive_feed_entries(
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


def extract_top_images(
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


def label_feeds(*args: Any, options: dict[str, Any] | None = None, **kwargs: Any):
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


def label_users(*args: Any, options: dict[str, Any] | None = None, **kwargs: Any):
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


def purge_expired_data(
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


def feed_scrape(*args: Any, options: dict[str, Any] | None = None, **kwargs: Any):
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


def setup_subscriptions(
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


def flag_duplicate_feeds(
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


def purge_duplicate_feed_urls(
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


def ignore_missed_top_images(
    *args: Any, options: dict[str, Any] | None = None, **kwargs: Any
):
    from dramatiq import Message

    options = options or {}
    broker.enqueue(
        Message(
            queue_name="rss_temple",
            actor_name="ignore_missed_top_images",
            args=args,
            kwargs=kwargs,
            options=options,
        )
    )
