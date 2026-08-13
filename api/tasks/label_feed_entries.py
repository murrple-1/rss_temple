import logging
import uuid as uuid_

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.db import transaction
from django.db.models.functions import Now
from django.utils import timezone

from api.lock_context import lock_context
from api.models import ClassifierLabel, ClassifierLabelFeedEntryCalculated, FeedEntry
from api.text_classifier.artifact import Artifact, ArtifactError, load_artifact
from api.text_classifier.classifier import predict
from api.text_classifier.prep_content import prep_for_classification

_logger = logging.getLogger("rss_temple.tasks.label_feed_entries")

_artifact: Artifact | None = None
_artifact_path: str | None = None


def _get_artifact() -> Artifact | None:
    """Load lazily, on first call, never at import time.

    `api/text_classifier/lang_detector.py` builds its detector at module import;
    that is what put lingua into every gunicorn worker. Do not copy it.

    Returns None (rather than raising) when no artifact has been trained yet
    -- there is deliberately no `classifier.json` shipped in this repository
    (see `api/tests/test_text_classifier.py`'s `ParityTestCase` docstring), so
    this is the expected state in production until a model is trained and
    deployed via `scripts/train_classifier.py`.
    """
    global _artifact, _artifact_path

    path = str(settings.CLASSIFIER_MODEL_PATH)
    if _artifact is None or _artifact_path != path:
        try:
            _artifact = load_artifact(path)
        except (OSError, ArtifactError):
            _logger.warning(
                "no classifier artifact at %r; a model has not been trained "
                "yet (see scripts/train_classifier.py). Skipping this run.",
                path,
            )
            return None
        _artifact_path = path
        _logger.info(
            "loaded classifier artifact %s (%d labels, %d features)",
            _artifact.model_fingerprint,
            len(_artifact.labels),
            len(_artifact.vocabulary),
        )
    return _artifact


def _label_uuids_by_text(artifact: Artifact) -> dict[str, uuid_.UUID]:
    known = dict(
        ClassifierLabel.objects.filter(text__in=artifact.labels).values_list(
            "text", "uuid"
        )
    )
    for label in artifact.labels:
        if label not in known:
            _logger.warning(
                "artifact label %r is not in the database; predictions for it "
                "will be discarded (see `manage.py checkclassifierlabels`)",
                label,
            )
    return known


def _expire_stale_rows() -> int:
    """Delete expired calculated rows AND reset the affected fingerprints.

    Without the reset the entry still looks processed, is never re-selected,
    and permanently loses its labels.
    """
    with transaction.atomic():
        expired = ClassifierLabelFeedEntryCalculated.objects.filter(
            expires_at__lte=Now()
        )
        feed_entry_ids = list(
            expired.values_list("feed_entry_id", flat=True).distinct()
        )
        if not feed_entry_ids:
            return 0

        expired.delete()
        FeedEntry.objects.filter(uuid__in=feed_entry_ids).update(
            classifier_model_fingerprint=""
        )

    return len(feed_entry_ids)


def label_feed_entries(
    db_limit: int = 1000, large_backlog_threshold: int = 50_000
) -> int:
    cache: BaseCache = caches["default"]

    with lock_context(cache, "label_feed_entries_lock"):
        artifact = _get_artifact()
        if artifact is None:
            return 0

        reset = _expire_stale_rows()
        if reset:
            _logger.info("reset %d entry(s) whose labels expired", reset)

        label_uuids = _label_uuids_by_text(artifact)
        max_labels: int = settings.CLASSIFIER_MAX_LABELS_PER_ENTRY
        weight_multiplier: float = settings.CLASSIFIER_LABEL_CALCULATED_WEIGHT
        expires_at = timezone.now() + settings.CLASSIFIER_LABEL_EXPIRY_INTERVAL

        # No order_by: ordering would force a sort over the whole backlog for no
        # benefit, whereas an unordered LIMIT lets Postgres stop early.
        pending = FeedEntry.objects.filter(
            language_id="ENG", is_archived=False
        ).exclude(classifier_model_fingerprint=artifact.model_fingerprint)

        total_remaining = pending.count()
        if total_remaining > large_backlog_threshold:
            _logger.warning(
                "large label-feed-entries backlog: %d is larger than threshold %d",
                total_remaining,
                large_backlog_threshold,
            )

        entries = list(pending.values("uuid", "title", "content")[:db_limit])
        if not entries:
            return 0

        rows: list[ClassifierLabelFeedEntryCalculated] = []
        for entry in entries:
            # Full, untruncated title/content -- prep_for_classification is
            # the only place truncation happens. Pre-slicing here would make
            # this inference path see different text than training saw for
            # the same document, a divergence no parity fixture can catch.
            text = prep_for_classification(entry["title"], entry["content"])
            for prediction in predict(artifact, text, max_labels):
                label_uuid = label_uuids.get(prediction.label)
                if label_uuid is None:
                    continue
                rows.append(
                    ClassifierLabelFeedEntryCalculated(
                        classifier_label_id=label_uuid,
                        feed_entry_id=entry["uuid"],
                        expires_at=expires_at,
                        weight=prediction.probability * weight_multiplier,
                    )
                )

        entry_uuids = [e["uuid"] for e in entries]
        with transaction.atomic():
            # Delete this batch's existing calculated rows before writing the
            # new ones. Without this, `bulk_create(..., ignore_conflicts=True)`
            # silently keeps the OLD row on every (classifier_label,
            # feed_entry) collision -- a retrained model's new weights are
            # discarded and a label the new model no longer predicts is never
            # removed, even though the entry below gets stamped with the new
            # fingerprint and so is never reconsidered again. Human votes live
            # in ClassifierLabelFeedEntryVote, a different table, so this
            # cannot touch them.
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry_id__in=entry_uuids
            ).delete()
            ClassifierLabelFeedEntryCalculated.objects.bulk_create(
                rows, ignore_conflicts=True
            )
            FeedEntry.objects.filter(uuid__in=entry_uuids).update(
                classifier_model_fingerprint=artifact.model_fingerprint
            )

        _logger.info("labelled %d entry(s), wrote %d row(s)", len(entries), len(rows))
        return len(entries)
