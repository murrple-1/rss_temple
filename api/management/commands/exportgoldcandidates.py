import json
from itertools import zip_longest
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import Feed, FeedEntry


class Command(BaseCommand):
    help = (
        "Emit a JSONL template of feed entries for hand-labelling into a gold "
        "evaluation set. Fill in the empty `labels` array on each line, then "
        "save the result as api/text_classifier/gold/gold_set.jsonl. Entries "
        "are stratified across feeds (round-robin) so a handful of "
        "high-volume publications cannot dominate the gold set the way they "
        "dominate the training corpus. Writes JSONL to stdout; anything "
        "informational goes to stderr, so the stream stays pipeable: "
        "`manage.py exportgoldcandidates --count 300 > gold_template.jsonl`"
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--count", type=int, default=300)
        parser.add_argument("--language", default="ENG")
        # 50,000 to match `exportcorpus --max-raw-content-chars`'s default:
        # both are raw-HTML export-payload safety valves, not the
        # classification-length cap (that lives in
        # `api.text_classifier.prep_content.MAX_CLASSIFICATION_CHARS`,
        # applied once to prepared text). A smaller raw slice here would
        # give the gold set (and `eval_classifier.py`, which scores against
        # it) less text than production ever sees for the same entry --
        # silently mismeasuring the model against a task easier than the
        # real one. See that module's docstring for the full 12.5:1
        # raw-to-prepared headroom rationale this default preserves.
        parser.add_argument("--excerpt-chars", type=int, default=50_000)

    def handle(self, *args: Any, **options: Any) -> None:
        count: int = options["count"]
        language: str = options["language"]
        excerpt_chars: int = options["excerpt_chars"]

        feed_uuids = list(Feed.objects.order_by("uuid").values_list("uuid", flat=True))
        if not feed_uuids or count <= 0:
            self.stderr.write(self.style.WARNING("emitted 0 candidate(s)"))
            return

        # Ceil division: each feed is asked for its share of `count`, so
        # round-robin below has enough from every feed to reach `count`
        # total even though it interleaves feeds one entry at a time.
        per_feed = -(-count // len(feed_uuids))

        per_feed_entries = [
            list(
                FeedEntry.objects.filter(
                    feed_id=feed_uuid, language_id=language, is_archived=False
                )
                .order_by("-published_at")
                .values("uuid", "title", "content", "feed_id")[:per_feed]
            )
            for feed_uuid in feed_uuids
        ]

        written = 0
        for round_entries in zip_longest(*per_feed_entries):
            for entry in round_entries:
                if written >= count:
                    break
                if entry is None:
                    # This feed ran out of entries before its share of
                    # `count`; skip it for this round rather than stopping
                    # the whole export early.
                    continue
                self.stdout.write(
                    json.dumps(
                        {
                            "uuid": str(entry["uuid"]),
                            "title": entry["title"],
                            "content_excerpt": entry["content"][:excerpt_chars],
                            "feed_id": str(entry["feed_id"]),
                            "labels": [],
                        },
                        separators=(",", ":"),
                    )
                )
                written += 1
            if written >= count:
                break

        self.stderr.write(self.style.SUCCESS(f"emitted {written} candidate(s)"))
