import datetime
import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from api.models import Feed, FeedEntry, Language


class ExportGoldCandidatesTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        english, _ = Language.objects.get_or_create(
            iso639_3="ENG", defaults={"iso639_1": "en", "name": "English"}
        )
        for f in range(3):
            feed = Feed.objects.create(
                feed_url=f"http://example.com/gold{f}.xml",
                title=f"Gold Feed {f}",
                home_url="http://example.com",
                published_at=now,
                updated_at=None,
                db_updated_at=None,
            )
            FeedEntry.objects.bulk_create(
                FeedEntry(
                    feed=feed,
                    published_at=now + datetime.timedelta(days=-i),
                    title=f"Entry {f}-{i}",
                    url=f"http://example.com/gold{f}-{i}.html",
                    content="y" * 900,
                    author_name="A",
                    db_updated_at=None,
                    is_archived=False,
                    language=english,
                )
                for i in range(4)
            )

    def _run(self, *args):
        out = StringIO()
        call_command("exportgoldcandidates", *args, stdout=out, stderr=StringIO())
        return [json.loads(line) for line in out.getvalue().splitlines() if line]

    def test_emits_template_rows_with_empty_labels(self):
        rows = self._run("--count", "6")
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(
                set(row), {"uuid", "title", "content_excerpt", "feed_id", "labels"}
            )
            self.assertEqual(row["labels"], [])

    def test_stratifies_across_feeds(self):
        rows = self._run("--count", "6")
        self.assertEqual(len({row["feed_id"] for row in rows}), 3)

    def test_truncates_the_excerpt(self):
        rows = self._run("--count", "3", "--excerpt-chars", "50")
        self.assertTrue(all(len(r["content_excerpt"]) <= 50 for r in rows))

    def test_no_feeds_emits_nothing(self):
        Feed.objects.all().delete()
        rows = self._run("--count", "6")
        self.assertEqual(rows, [])

    def test_respects_language_filter(self):
        other, _ = Language.objects.get_or_create(
            iso639_3="FRA", defaults={"iso639_1": "fr", "name": "French"}
        )
        rows = self._run("--count", "50", "--language", other.iso639_3)
        self.assertEqual(rows, [])

    def test_uuids_are_unique_and_no_duplicates_across_feeds(self):
        rows = self._run("--count", "12")
        uuids = [row["uuid"] for row in rows]
        self.assertEqual(len(uuids), len(set(uuids)))
