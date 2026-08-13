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
    # Offset 30 minutes after `label_feeds`' default (`0 0 * * *`) on purpose:
    # `label_users` aggregates `ClassifierLabelFeedCalculated`, the table
    # `label_feeds` deletes-then-repopulates each run. Under
    # `BlockingScheduler`'s default 10-thread executor these two jobs run
    # concurrently if left on the same crontab, and `label_users` can read
    # that table while `label_feeds` is between its delete and its
    # `bulk_create`, producing an empty cycle for `label_users`. It
    # self-heals the next night, but staggering the defaults avoids it for
    # free.
    crontab = serializers.CharField(default="30 0 * * *")  # 30 minutes after midnight
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


class _LabelFeedEntriesSerializer(serializers.Serializer):
    # Every 5 minutes, deliberately not aligned with `label_feeds`' midnight
    # or `label_users`' 00:30-past-midnight crontabs: those two are staggered
    # relative to *each other* because one reads a table the other
    # deletes-then-repopulates every night. This job reads/writes entirely
    # different tables (FeedEntry.classifier_model_fingerprint and
    # ClassifierLabelFeedEntryCalculated) and guards its own overlap with the
    # "label_feed_entries_lock" redis lock, so it has nothing to race with
    # either of them and a five-minute cadence is free to pick independently.
    # At db_limit 1000 a ~250,000-entry backlog needs 250 runs, which is
    # roughly a day at this cadence.
    # This whole serializer is optional on `SetupSerializer` (see
    # `label_feed_entries = _LabelFeedEntriesSerializer(required=False)`
    # below): `schedulerdaemon.json` is gitignored, so an existing
    # production config predating this job has no `label_feed_entries`
    # key at all. Every field on it already has a default, so "optional"
    # just means the job schedules with those defaults -- see
    # `SetupSerializer.create` for how a missing key is resolved to them
    # rather than raising `This field is required.` for the *whole*
    # scheduler daemon.
    crontab = serializers.CharField(default="*/5 * * * *")
    dbLimit = serializers.IntegerField(source="db_limit", default=1000)
    largeBacklogThreshold = serializers.IntegerField(
        source="large_backlog_threshold", default=50000
    )

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.label_feed_entries,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="label_feed_entries",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "db_limit": validated_data["db_limit"],
                "large_backlog_threshold": validated_data["large_backlog_threshold"],
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


class _IgnoreMissedTopImagesSerializer(serializers.Serializer):
    crontab = serializers.CharField(
        default="0 0 * * *"
    )  # every 1st and 15th, at midnight
    sinceIntervalDays = serializers.IntegerField(
        source="since_interval_days", default=14
    )

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.ignore_missed_top_images,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="ignore_missed_top_images",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "since_interval_days": validated_data["since_interval_days"],
            },
        )
        return job


class SetupSerializer(serializers.Serializer):
    delete_old_job_executions = _DeleteOldJobExecutionsSerializer()
    archive_feed_entries = _ArchiveFeedEntriesSerializer()
    extract_top_images = _ExtractTopImagesSerializer()
    label_feeds = _LabelFeedsSerializer()
    label_feed_entries = _LabelFeedEntriesSerializer(required=False)
    label_users = _LabelUsersSerializer()
    feed_scrape = _FeedScrapeSerializer()
    setup_subscriptions = _SetupSubscriptionsSerializer()
    purge_expired_data = _PurgeExpiredDataSerializer()
    flag_duplicate_feeds = _FlagDuplicateFeedsSerializer()
    purge_duplicate_feed_urls = _PurgeDuplicateFeedUrlsSerializer()
    ignore_missed_top_images = _IgnoreMissedTopImagesSerializer()

    def create(self, validated_data: Any) -> Any:
        jobs: list[Any] = []
        for field_name, serializer in self.fields.items():
            assert isinstance(serializer, serializers.Serializer)
            field_data = validated_data.get(field_name)
            if field_data is None:
                # `required=False` fields (currently only
                # `label_feed_entries`) are simply absent from
                # `validated_data` when their key is missing from the
                # config, rather than being filled in with their nested
                # defaults -- DRF only auto-fills defaults for fields that
                # declare one, and a `default=` on a nested Serializer
                # field would bypass that child's own field-level
                # validation/defaulting entirely (it would hand back the
                # raw default object unvalidated). Running an empty `{}`
                # through the child serializer itself is what actually
                # produces its per-field defaults (crontab, dbLimit, etc.).
                field_serializer = serializer.__class__(data={})
                field_serializer.is_valid(raise_exception=True)
                field_data = field_serializer.validated_data
            job = serializer.create(field_data)
            jobs.append(job)

        return jobs
