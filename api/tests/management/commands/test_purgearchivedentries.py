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


class PurgeArchivedEntriesTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        self.user = User.objects.create_user("user@test.com", None)
        self.label = ClassifierLabel.objects.create(text="Label 1")

        self.feed = Feed.objects.create(
            feed_url="http://example.com/purge.xml",
            title="Purge Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )

        def make(name: str, days_ago: int, is_archived: bool) -> FeedEntry:
            return FeedEntry.objects.create(
                feed=self.feed,
                published_at=now - datetime.timedelta(days=days_ago),
                title=name,
                url=f"http://example.com/{name}.html",
                content="content",
                author_name="John Doe",
                db_updated_at=None,
                is_archived=is_archived,
            )

        self.old_archived = make("old_archived", 365 * 4, True)
        self.old_archived_2 = make("old_archived_2", 365 * 5, True)
        self.old_unarchived = make("old_unarchived", 365 * 4, False)
        self.recent_archived = make("recent_archived", 365, True)
        self.old_favorited = make("old_favorited", 365 * 4, True)
        self.old_voted = make("old_voted", 365 * 4, True)

        self.user.favorite_feed_entries.add(self.old_favorited)
        ClassifierLabelFeedEntryVote.objects.create(
            feed_entry=self.old_voted, classifier_label=self.label, user=self.user
        )

    def _remaining_titles(self) -> set[str]:
        return set(FeedEntry.objects.values_list("title", flat=True))

    def test_dry_run_is_the_default_and_deletes_nothing(self):
        out = StringIO()
        call_command("purgearchivedentries", stderr=out)

        self.assertEqual(FeedEntry.objects.count(), 6)
        self.assertIn("matching entries: 3", out.getvalue())

    def test_no_dry_run_deletes_only_old_archived_unprotected_entries(self):
        call_command("purgearchivedentries", "--no-dry-run", stderr=StringIO())

        self.assertEqual(
            self._remaining_titles(),
            {
                "old_unarchived",
                "recent_archived",
                "old_favorited",
            },
        )
        self.assertFalse(ClassifierLabelFeedEntryVote.objects.exists())

    def test_older_than_years(self):
        call_command(
            "purgearchivedentries",
            "--older-than-years",
            "1",
            "--no-dry-run",
            stderr=StringIO(),
        )

        self.assertNotIn("recent_archived", self._remaining_titles())

    def test_before(self):
        before = (timezone.now() - datetime.timedelta(days=365 * 4 + 30)).date()
        call_command(
            "purgearchivedentries",
            "--before",
            before.isoformat(),
            "--no-dry-run",
            stderr=StringIO(),
        )

        remaining = self._remaining_titles()
        self.assertNotIn("old_archived_2", remaining)
        self.assertIn("old_archived", remaining)

    def test_before_and_older_than_years_are_exclusive(self):
        with self.assertRaises(CommandError):
            call_command(
                "purgearchivedentries",
                "--before",
                "2020-01-01",
                "--older-than-years",
                "2",
                stderr=StringIO(),
            )

    def test_future_cutoff_raises(self):
        future = (timezone.now() + datetime.timedelta(days=30)).date()
        with self.assertRaises(CommandError):
            call_command(
                "purgearchivedentries",
                "--before",
                future.isoformat(),
                "--no-dry-run",
                stderr=StringIO(),
            )

        self.assertEqual(FeedEntry.objects.count(), 6)

    def test_invalid_older_than_years_raises(self):
        for years in ("0", "-1"):
            with self.assertRaises(CommandError):
                call_command(
                    "purgearchivedentries",
                    "--older-than-years",
                    years,
                    "--no-dry-run",
                    stderr=StringIO(),
                )

        self.assertEqual(FeedEntry.objects.count(), 6)

    def test_invalid_batch_size_raises(self):
        for batch_size in ("0", "-1"):
            with self.assertRaises(CommandError):
                call_command(
                    "purgearchivedentries",
                    "--no-dry-run",
                    "--batch-size",
                    batch_size,
                    stderr=StringIO(),
                )

        self.assertEqual(FeedEntry.objects.count(), 6)

    def test_batching_deletes_everything(self):
        out = StringIO()
        call_command(
            "purgearchivedentries",
            "--no-dry-run",
            "--batch-size",
            "1",
            stderr=out,
        )

        self.assertNotIn("old_archived", self._remaining_titles())
        self.assertNotIn("old_archived_2", self._remaining_titles())
        self.assertIn("deleted 3 feed entry(s)", out.getvalue())
