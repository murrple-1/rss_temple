import datetime
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryVote,
    Feed,
    FeedEntry,
    User,
)


class PurgeBulkVotesTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        self.bulk_user = User.objects.create_user("bulk@test.com", None)
        self.real_user = User.objects.create_user("real@test.com", None)
        self.label = ClassifierLabel.objects.create(text="Label 1")

        feed = Feed.objects.create(
            feed_url="http://example.com/purge.xml",
            title="Purge Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        self.feed_entries = FeedEntry.objects.bulk_create(
            FeedEntry(
                feed=feed,
                published_at=now + datetime.timedelta(days=-i),
                title=f"Entry {i}",
                url=f"http://example.com/purge{i}.html",
                content="content",
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
            )
            for i in range(4)
        )

        ClassifierLabelFeedEntryVote.objects.bulk_create(
            ClassifierLabelFeedEntryVote(
                feed_entry=fe, classifier_label=self.label, user=self.bulk_user
            )
            for fe in self.feed_entries[0:3]
        )
        ClassifierLabelFeedEntryVote.objects.create(
            feed_entry=self.feed_entries[3],
            classifier_label=self.label,
            user=self.real_user,
        )

    def test_dry_run_is_the_default_and_deletes_nothing(self):
        out = StringIO()
        call_command("purgebulkvotes", "--user-email", "bulk@test.com", stderr=out)

        self.assertEqual(ClassifierLabelFeedEntryVote.objects.count(), 4)
        self.assertIn("3", out.getvalue())

    def test_no_dry_run_deletes_only_the_named_account(self):
        call_command(
            "purgebulkvotes",
            "--user-email",
            "bulk@test.com",
            "--no-dry-run",
            stderr=StringIO(),
        )

        self.assertEqual(
            ClassifierLabelFeedEntryVote.objects.filter(user=self.bulk_user).count(), 0
        )
        self.assertEqual(
            ClassifierLabelFeedEntryVote.objects.filter(user=self.real_user).count(), 1
        )

    def test_unknown_email_raises(self):
        with self.assertRaises(CommandError):
            call_command(
                "purgebulkvotes",
                "--user-email",
                "nobody@test.com",
                stderr=StringIO(),
            )

    def test_batching_deletes_everything(self):
        call_command(
            "purgebulkvotes",
            "--user-email",
            "bulk@test.com",
            "--no-dry-run",
            "--batch-size",
            "1",
            stderr=StringIO(),
        )

        self.assertEqual(
            ClassifierLabelFeedEntryVote.objects.filter(user=self.bulk_user).count(), 0
        )
