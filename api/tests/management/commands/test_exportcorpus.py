import datetime
import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryVote,
    Feed,
    FeedEntry,
    Language,
    User,
)


class ExportCorpusTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        self.english, _ = Language.objects.get_or_create(
            iso639_3="ENG", defaults={"iso639_1": "en", "name": "English"}
        )
        self.french, _ = Language.objects.get_or_create(
            iso639_3="FRA", defaults={"iso639_1": "fr", "name": "French"}
        )
        self.user = User.objects.create_user("corpus@test.com", None)
        self.label = ClassifierLabel.objects.create(text="Label 1")

        self.feed = Feed.objects.create(
            feed_url="http://example.com/corpus.xml",
            title="Corpus Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        self.entries = FeedEntry.objects.bulk_create(
            FeedEntry(
                feed=self.feed,
                published_at=now + datetime.timedelta(days=-i),
                title=f"Entry {i}",
                url=f"http://example.com/corpus{i}.html",
                content="x" * 100,
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
                language=self.english,
            )
            for i in range(5)
        )
        FeedEntry.objects.create(
            feed=self.feed,
            published_at=now,
            title="French Entry",
            url="http://example.com/fr.html",
            content="bonjour",
            author_name="Jean",
            db_updated_at=None,
            is_archived=False,
            language=self.french,
        )
        ClassifierLabelFeedEntryVote.objects.create(
            feed_entry=self.entries[0], classifier_label=self.label, user=self.user
        )

    def _run(self, *args):
        out = StringIO()
        call_command("exportcorpus", *args, stdout=out, stderr=StringIO())
        return [json.loads(line) for line in out.getvalue().splitlines() if line]

    def test_emits_one_json_object_per_entry(self):
        rows = self._run()
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(
                set(row),
                {"uuid", "title", "content", "feed_id", "language", "vote_labels"},
            )

    def test_filters_to_the_requested_language(self):
        rows = self._run()
        self.assertTrue(all(row["language"] == "ENG" for row in rows))

    def test_respects_per_feed(self):
        rows = self._run("--per-feed", "2")
        self.assertEqual(len(rows), 2)

    def test_respects_max_total(self):
        rows = self._run("--max-total", "3")
        self.assertEqual(len(rows), 3)

    def test_truncates_content(self):
        # Renamed from --max-content-chars: this is a raw-payload safety
        # valve, not the classification-length cap (that one lives in
        # `prep_content.MAX_CLASSIFICATION_CHARS`, applied to prepared text
        # by every caller identically -- see that module's docstring).
        rows = self._run("--max-raw-content-chars", "10")
        self.assertTrue(all(len(row["content"]) <= 10 for row in rows))

    def test_includes_vote_labels(self):
        rows = self._run()
        by_uuid = {row["uuid"]: row for row in rows}
        self.assertEqual(by_uuid[str(self.entries[0].uuid)]["vote_labels"], ["Label 1"])

    def test_excludes_archived_entries(self):
        FeedEntry.objects.filter(uuid=self.entries[0].uuid).update(is_archived=True)
        rows = self._run()
        self.assertEqual(len(rows), 4)

    def test_streams_per_feed_queries_with_a_limit_rather_than_loading_all_rows(self):
        # Pins the whole point of the per-feed sampling design: the per-feed
        # entry query must carry a LIMIT (SQL "LIMIT") rather than pulling
        # every row for a feed into memory and slicing in Python. If this
        # ever regresses to something like `.order_by("?")` or a plain
        # `list(...)` without a LIMIT, this test should fail.
        out = StringIO()
        with CaptureQueriesContext(connection) as ctx:
            call_command("exportcorpus", stdout=out, stderr=StringIO())

        entry_queries = [
            q["sql"]
            for q in ctx.captured_queries
            if '"api_feedentry"' in q["sql"].lower()
            and "select" in q["sql"].lower()
            and "classifierlabelfeedentryvote" not in q["sql"].lower()
        ]
        self.assertTrue(entry_queries, "expected at least one FeedEntry SELECT query")
        for sql in entry_queries:
            self.assertIn(
                "LIMIT",
                sql.upper(),
                f"expected per-feed FeedEntry query to carry a LIMIT, got: {sql}",
            )

    def test_query_count_scales_with_feeds_not_entries(self):
        # A second, independent pin on the same property: adding many more
        # entries to the same single feed must not increase the number of
        # queries issued, since entries are fetched per-feed with a LIMIT
        # rather than the full result set being materialised and iterated.
        with CaptureQueriesContext(connection) as ctx_before:
            call_command("exportcorpus", stdout=StringIO(), stderr=StringIO())
        queries_before = len(ctx_before.captured_queries)

        now = timezone.now()
        FeedEntry.objects.bulk_create(
            FeedEntry(
                feed=self.feed,
                published_at=now + datetime.timedelta(days=-100 - i),
                title=f"Bulk Entry {i}",
                url=f"http://example.com/bulk{i}.html",
                content="y" * 100,
                author_name="Jane Doe",
                db_updated_at=None,
                is_archived=False,
                language=self.english,
            )
            for i in range(500)
        )

        with CaptureQueriesContext(connection) as ctx_after:
            call_command("exportcorpus", stdout=StringIO(), stderr=StringIO())
        queries_after = len(ctx_after.captured_queries)

        self.assertEqual(queries_before, queries_after)
