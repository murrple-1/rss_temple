from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from rest_framework import serializers

from api.management.commands import _schedulerdaemon_jobs as jobs


class _DeleteOldJobExecutionsSerializer(serializers.Serializer):
    crontab = serializers.CharField(default="0 0 * * 0")  # every Sunday at midnight
    maxAge = serializers.FloatField(source="max_age", default=604800)

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.delete_old_job_executions,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={"max_age": validated_data["max_age"]},
        )

        return job


class _ArchiveFeedEntriesSerializer(serializers.Serializer):
    crontab = serializers.CharField(
        default="*/30 * * * *"
    )  # every half-hour, on the half-hour
    limit = serializers.IntegerField(default=1000)

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.archive_feed_entries,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="archive_feed_entries",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "limit": validated_data["limit"],
            },
        )
        return job


class _ExtractTopImagesSerializer(serializers.Serializer):
    intervalSeconds = serializers.IntegerField(source="interval_seconds", default=30)
    maxProcessingAttempts = serializers.IntegerField(
        source="max_processing_attempts", default=3
    )
    minImageByteCount = serializers.IntegerField(
        source="min_image_byte_count", default=4500
    )
    minImageWidth = serializers.IntegerField(source="min_image_width", default=250)
    minImageHeight = serializers.IntegerField(source="min_image_height", default=250)
    responseMaxByteCount = serializers.IntegerField(
        source="response_max_byte_count", default=-1
    )
    dbLimit = serializers.IntegerField(source="db_limit", default=50)
    since = serializers.CharField(allow_null=True, default=None)
    timeoutPerRequest = serializers.IntegerField(
        source="timeout_per_request", default=5
    )
    largeBacklogThreshold = serializers.IntegerField(
        source="large_backlog_threshold", default=200
    )

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.extract_top_images,
            trigger=IntervalTrigger(seconds=validated_data["interval_seconds"]),
            id="extract_top_images",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            args=(validated_data["response_max_byte_count"],),
            kwargs={
                "max_processing_attempts": validated_data["max_processing_attempts"],
                "min_image_byte_count": validated_data["min_image_byte_count"],
                "min_image_width": validated_data["min_image_width"],
                "min_image_height": validated_data["min_image_height"],
                "db_limit": validated_data["db_limit"],
                "since": validated_data["since"],
                "timeout_per_request": validated_data["timeout_per_request"],
                "large_backlog_threshold": validated_data["large_backlog_threshold"],
            },
        )
        return job


class _LabelFeedsSerializer(serializers.Serializer):
    crontab = serializers.CharField(default="0 0 * * *")  # every midnight
    topX = serializers.IntegerField(source="top_x", default=3)

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.label_feeds,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="label_feeds",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "top_x": validated_data["top_x"],
            },
        )
        return job


class _LabelUsersSerializer(serializers.Serializer):
    crontab = serializers.CharField(default="0 0 * * *")  # every midnight
    topX = serializers.IntegerField(source="top_x", default=3)

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.label_users,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="label_users",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "top_x": validated_data["top_x"],
            },
        )
        return job


class _FeedScrapeSerializer(serializers.Serializer):
    intervalSeconds = serializers.IntegerField(source="interval_seconds", default=30)
    maxAge = serializers.IntegerField(
        source="max_age", default=(1000 * 25)
    )  # 25 seconds
    responseMaxByteCount = serializers.IntegerField(
        source="response_max_byte_count", default=-1
    )
    dbLimit = serializers.IntegerField(source="db_limit", default=1000)
    isDeadMaxIntervalSeconds = serializers.FloatField(
        source="is_dead_max_interval_seconds",
        default=settings.FEED_IS_DEAD_MAX_INTERVAL.total_seconds(),
    )
    shouldScrapeDeadFeeds = serializers.BooleanField(
        source="should_scrape_dead_feeds", default=False
    )
    logExceptionTraceback = serializers.BooleanField(
        source="log_exception_traceback", default=False
    )

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.feed_scrape,
            trigger=IntervalTrigger(seconds=validated_data["interval_seconds"]),
            id="feed_scrape",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            args=(
                validated_data["response_max_byte_count"],
                validated_data["should_scrape_dead_feeds"],
            ),
            kwargs={
                "options": {
                    "max_age": validated_data["max_age"],
                },
                "db_limit": validated_data["db_limit"],
                "is_dead_max_interval_seconds": validated_data[
                    "is_dead_max_interval_seconds"
                ],
                "log_exception_traceback": validated_data["log_exception_traceback"],
            },
        )
        return job


class _SetupSubscriptionsSerializer(serializers.Serializer):
    intervalSeconds = serializers.IntegerField(source="interval_seconds", default=30)
    maxAge = serializers.IntegerField(
        source="max_age", default=(1000 * 25)
    )  # 25 seconds
    responseMaxByteCount = serializers.IntegerField(
        source="response_max_byte_count", default=-1
    )

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.setup_subscriptions,
            trigger=IntervalTrigger(seconds=validated_data["interval_seconds"]),
            id="setup_subscriptions",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            args=(validated_data["response_max_byte_count"],),
            kwargs={
                "options": {
                    "max_age": validated_data["max_age"],
                },
            },
        )
        return job


class _PurgeExpiredDataSerializer(serializers.Serializer):
    crontab = serializers.CharField(
        default="0 0 */15 * *"
    )  # every 1st and 15th, at midnight

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.purge_expired_data,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="purge_expired_data",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
        )
        return job


class _FlagDuplicateFeedsSerializer(serializers.Serializer):
    crontab = serializers.CharField(default="0 0 * * *")  # every midnight
    feedCount = serializers.IntegerField(source="feed_count", default=1000)
    entryCompareCount = serializers.IntegerField(
        source="entry_compare_count", default=50
    )
    entryIntersectionThreshold = serializers.IntegerField(
        source="entry_intersection_threshold", default=5
    )

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.flag_duplicate_feeds,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="flag_duplicate_feeds",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "feed_count": validated_data["feed_count"],
                "entry_compare_count": validated_data["entry_compare_count"],
                "entry_intersection_threshold": validated_data[
                    "entry_intersection_threshold"
                ],
            },
        )
        return job


class _PurgeDuplicateFeedUrlsSerializer(serializers.Serializer):
    crontab = serializers.CharField(
        default="0 0 */15 * *"
    )  # every 1st and 15th, at midnight

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.purge_duplicate_feed_urls,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="purge_duplicate_feed_urls",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
        )
        return job


class SetupSerializer(serializers.Serializer):
    delete_old_job_executions = _DeleteOldJobExecutionsSerializer()
    archive_feed_entries = _ArchiveFeedEntriesSerializer()
    extract_top_images = _ExtractTopImagesSerializer()
    label_feeds = _LabelFeedsSerializer()
    label_users = _LabelUsersSerializer()
    feed_scrape = _FeedScrapeSerializer()
    setup_subscriptions = _SetupSubscriptionsSerializer()
    purge_expired_data = _PurgeExpiredDataSerializer()
    flag_duplicate_feeds = _FlagDuplicateFeedsSerializer()
    purge_duplicate_feed_urls = _PurgeDuplicateFeedUrlsSerializer()

    def create(self, validated_data: Any) -> Any:
        jobs: list[Any] = []
        for field_name, serializer in self.fields.items():
            assert isinstance(serializer, serializers.Serializer)
            job = serializer.create(validated_data[field_name])
            jobs.append(job)

        return jobs
