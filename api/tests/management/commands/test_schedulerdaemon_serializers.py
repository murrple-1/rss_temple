from apscheduler.schedulers.background import BackgroundScheduler
from django.test import SimpleTestCase

from api.management.commands import _schedulerdaemon_serializers as serializers

# Mirrors master's `schedulerdaemon.example.json` -- i.e. a config file that
# predates `label_feed_entries` and therefore has no key for it at all.
# `schedulerdaemon.json` is gitignored, so any existing production
# deployment's real config looks exactly like this with respect to that key.
_PRE_EXISTING_CONFIG = {
    "delete_old_job_executions": {},
    "archive_feed_entries": {},
    "extract_top_images": {},
    "label_feeds": {},
    "label_users": {},
    "feed_scrape": {"shouldScrapeDeadFeeds": True},
    "setup_subscriptions": {},
    "purge_expired_data": {},
    "flag_duplicate_feeds": {},
    "purge_duplicate_feed_urls": {},
    "ignore_missed_top_images": {},
}


class SetupSerializerMissingLabelFeedEntriesTestCase(SimpleTestCase):
    """Regression for the finding that deploying this branch's
    `label_feed_entries` scheduler job stops the ENTIRE scheduler daemon on
    any pre-existing config: `label_feed_entries` used to be a required
    nested field on `SetupSerializer`, and `schedulerdaemon.json` is
    gitignored, so production keeps running its own copy without the new
    key. Validation used to fail with "This field is required.", which
    `manage.py schedulerdaemon` turns into a `CommandError`, refusing to
    start the whole daemon -- not just skip the new job -- taking
    `feed_scrape`, `archive_feed_entries`, and everything else down with it.
    """

    def test_config_without_label_feed_entries_key_validates(self):
        serializer = serializers.SetupSerializer(
            data=_PRE_EXISTING_CONFIG, context={"scheduler": None}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_missing_label_feed_entries_schedules_with_documented_defaults(self):
        scheduler = BackgroundScheduler()
        serializer = serializers.SetupSerializer(
            data=_PRE_EXISTING_CONFIG, context={"scheduler": scheduler}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        job = scheduler.get_job("label_feed_entries")
        self.assertIsNotNone(job)
        self.assertEqual(job.kwargs["db_limit"], 1000)
        self.assertEqual(job.kwargs["large_backlog_threshold"], 50000)
        self.assertEqual(
            str(job.trigger),
            "cron[month='*', day='*', day_of_week='*', hour='*', minute='*/5']",
        )
