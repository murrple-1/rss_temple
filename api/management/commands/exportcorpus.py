import json
import uuid as uuid_
from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import ClassifierLabelFeedEntryVote, Feed, FeedEntry


class Command(BaseCommand):
    help = (
        "Export feed entries as JSONL for off-box classifier training. "
        "Sampling is per-feed rather than globally random, which is both "
        "index-friendly and produces a corpus balanced across publications. "
        "Pipe to gzip: `manage.py exportcorpus | gzip > corpus.jsonl.gz`"
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--per-feed", type=int, default=50)
        parser.add_argument("--max-total", type=int, default=200_000)
        parser.add_argument("--language", default="ENG")
        # A generous export-payload safety valve ONLY -- this is not where
        # classification-text truncation happens. It used to slice raw
        # content to 4000 chars (the classification length cap), which cut
        # HTML mid-tag/mid-entity and made the trainer's
        # `prep_for_classification` output diverge from whatever a
        # production inference path would produce from the same, untruncated
        # entry -- a training/inference text-prep mismatch no parity
        # fixture can detect, because it happens before either side of that
        # comparison runs. The real cap is
        # `api.text_classifier.prep_content.MAX_CLASSIFICATION_CHARS`,
        # applied to prepared (stripped) text by `prep_for_classification`
        # itself, identically for every caller. This flag just bounds how
        # much raw, unprepared content one JSONL line can contain.
        parser.add_argument("--max-raw-content-chars", type=int, default=50_000)

    def handle(self, *args: Any, **options: Any) -> None:
        per_feed: int = options["per_feed"]
        max_total: int = options["max_total"]
        language: str = options["language"]
        max_raw_content_chars: int = options["max_raw_content_chars"]
        verbosity: int = options["verbosity"]

        written = 0

        for feed_uuid in Feed.objects.values_list("uuid", flat=True).iterator():
            if written >= max_total:
                break

            remaining = max_total - written
            entries = list(
                FeedEntry.objects.filter(
                    feed_id=feed_uuid,
                    language_id=language,
                    is_archived=False,
                )
                .order_by("-published_at")
                .values("uuid", "title", "content", "feed_id")[
                    : min(per_feed, remaining)
                ]
            )
            if not entries:
                continue

            votes = self._vote_labels([e["uuid"] for e in entries])

            for entry in entries:
                self.stdout.write(
                    json.dumps(
                        {
                            "uuid": str(entry["uuid"]),
                            "title": entry["title"],
                            "content": entry["content"][:max_raw_content_chars],
                            "feed_id": str(entry["feed_id"]),
                            "language": language,
                            "vote_labels": votes.get(entry["uuid"], []),
                        },
                        separators=(",", ":"),
                    )
                )
                written += 1

        if verbosity >= 1:
            self.stderr.write(self.style.SUCCESS(f"exported {written} entry(s)"))

    def _vote_labels(
        self, feed_entry_uuids: list[uuid_.UUID]
    ) -> dict[uuid_.UUID, list[str]]:
        labels: defaultdict[uuid_.UUID, list[str]] = defaultdict(list)
        for row in (
            ClassifierLabelFeedEntryVote.objects.filter(
                feed_entry_id__in=feed_entry_uuids
            )
            .values("feed_entry_id", "classifier_label__text")
            .iterator()
        ):
            labels[row["feed_entry_id"]].append(row["classifier_label__text"])
        return labels
