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

    def test_round_robin_touches_every_feed_even_when_sizes_are_unequal(self):
        # `setUp` gives every feed the same 4 entries, so a discriminating
        # regression needs unequal feeds: replacing the round-robin
        # interleave with sequential concatenation would still pass every
        # test above (three EQUAL feeds can't tell "round-robin" apart from
        # "first feed's share, then the next's"), because either strategy
        # visits all three feeds by the time `count` entries are collected.
        #
        # With one big feed (10 entries) and two single-entry feeds, and
        # `--count 6`: round-robin's per-feed share is ceil(6/3) = 2, so it
        # draws from feed A, then B, then C, then back to A, ... and reaches
        # all 3 feeds well before hitting 6. Sequential concatenation
        # (ordered by feed uuid, as this command orders feeds) would drain
        # up to `per_feed` from the FIRST feed alone before ever moving on;
        # if feed A happens to be big enough (as it is here), that means
        # sequential concatenation never even reaches feed B or C within
        # the same 6-row budget.
        Feed.objects.all().delete()
        FeedEntry.objects.all().delete()
        now = timezone.now()
        english, _ = Language.objects.get_or_create(
            iso639_3="ENG", defaults={"iso639_1": "en", "name": "English"}
        )

        big_feed = Feed.objects.create(
            feed_url="http://example.com/big.xml",
            title="Big Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        FeedEntry.objects.bulk_create(
            FeedEntry(
                feed=big_feed,
                published_at=now + datetime.timedelta(days=-i),
                title=f"Big {i}",
                url=f"http://example.com/big{i}.html",
                content="z" * 900,
                author_name="A",
                db_updated_at=None,
                is_archived=False,
                language=english,
            )
            for i in range(10)
        )
        small_feeds = []
        for label in ("small-a", "small-b"):
            small_feed = Feed.objects.create(
                feed_url=f"http://example.com/{label}.xml",
                title=label,
                home_url="http://example.com",
                published_at=now,
                updated_at=None,
                db_updated_at=None,
            )
            FeedEntry.objects.create(
                feed=small_feed,
                published_at=now,
                title=label,
                url=f"http://example.com/{label}.html",
                content="z" * 900,
                author_name="A",
                db_updated_at=None,
                is_archived=False,
                language=english,
            )
            small_feeds.append(small_feed)

        rows = self._run("--count", "6")
        # Round-robin's per-feed share is ceil(6/3) = 2 -- capped
        # per-feed, regardless of any single feed's actual size -- so the
        # big feed contributes only 2 of its 10 entries here, same as if it
        # had exactly 2. Total available is therefore 2 (big) + 1 (small-a)
        # + 1 (small-b) = 4, short of the requested 6, but from all 3 feeds.
        # Sequential concatenation of feeds in order, with no per-feed cap
        # (the natural way to write "just take entries until you have
        # `count`" once you no longer need round-robin's fairness bound),
        # would instead drain up to 6 entries from the big feed ALONE before
        # ever considering feed B or C -- a single feed's entries flooding
        # the gold set, exactly what stratification exists to prevent.
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            {row["feed_id"] for row in rows},
            {str(big_feed.uuid), str(small_feeds[0].uuid), str(small_feeds[1].uuid)},
        )
