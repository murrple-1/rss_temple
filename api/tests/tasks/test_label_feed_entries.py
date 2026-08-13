import datetime
import json
import logging
import os
import tempfile
from typing import ClassVar

from django.test import TestCase, override_settings
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryCalculated,
    Feed,
    FeedEntry,
    Language,
)
from api.tasks.label_feed_entries import label_feed_entries
from api.text_classifier.artifact import VectorizerConfig, dump_artifact

_VECTORIZER_KWARGS = {
    "token_pattern": r"(?u)\b\w\w+\b",
    "ngram_range": (1, 2),
    "lowercase": True,
    "sublinear_tf": True,
    "norm": "l2",
    "stop_words": (),
    "binary": False,
    "strip_accents": None,
    "analyzer": "word",
}


class LabelFeedEntriesTestCase(TestCase):
    old_app_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)

    def setUp(self):
        now = timezone.now()
        self.english, _ = Language.objects.get_or_create(
            iso639_3="ENG", defaults={"iso639_1": "en", "name": "English"}
        )
        self.french, _ = Language.objects.get_or_create(
            iso639_3="FRA", defaults={"iso639_1": "fr", "name": "French"}
        )
        # "Gaming" and "Music" are already seeded by migration 0016 (the
        # initial taxonomy labels), so get_or_create rather than create --
        # a bare create() collides with the UNIQUE constraint on `text`.
        self.gaming, _ = ClassifierLabel.objects.get_or_create(text="Gaming")
        self.orphan, _ = ClassifierLabel.objects.get_or_create(text="Music")

        self.feed = Feed.objects.create(
            feed_url="http://example.com/lfe.xml",
            title="LFE Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        self.matching = FeedEntry.objects.create(
            feed=self.feed,
            published_at=now,
            title="nintendo",
            url="http://example.com/lfe1.html",
            content="nintendo",
            author_name="A",
            db_updated_at=None,
            is_archived=False,
            language=self.english,
        )
        self.non_matching = FeedEntry.objects.create(
            feed=self.feed,
            published_at=now,
            title="zzzz",
            url="http://example.com/lfe2.html",
            content="zzzz",
            author_name="A",
            db_updated_at=None,
            is_archived=False,
            language=self.english,
        )
        self.french_entry = FeedEntry.objects.create(
            feed=self.feed,
            published_at=now,
            title="nintendo",
            url="http://example.com/lfe3.html",
            content="nintendo",
            author_name="A",
            db_updated_at=None,
            is_archived=False,
            language=self.french,
        )

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.model_path = os.path.join(self.tmpdir.name, "classifier.json")
        self.fingerprint = dump_artifact(
            self.model_path,
            labels=["Gaming", "Music", "Ghost Label"],
            vocabulary_terms=["nintendo"],
            idf=[1.0],
            # Gaming fires on "nintendo"; Music and Ghost Label never fire.
            coef=[10.0, -10.0, -10.0],
            intercept=[0.0, 0.0, 0.0],
            thresholds=[1.0, 1.0, 1.0],
            vectorizer=VectorizerConfig(**_VECTORIZER_KWARGS),
            taxonomy_fingerprint="sha256:test",
            training={},
        )

    def _settings(self, **overrides):
        base = {
            "CLASSIFIER_MODEL_PATH": self.model_path,
            "CLASSIFIER_MAX_LABELS_PER_ENTRY": 3,
            "CLASSIFIER_LABEL_CALCULATED_WEIGHT": 0.5,
            "CLASSIFIER_LABEL_EXPIRY_INTERVAL": datetime.timedelta(days=365),
        }
        base.update(overrides)
        return override_settings(**base)

    def test_writes_weighted_labels(self):
        with self._settings():
            label_feed_entries()

        rows = list(
            ClassifierLabelFeedEntryCalculated.objects.filter(feed_entry=self.matching)
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].classifier_label_id, self.gaming.uuid)
        self.assertGreater(rows[0].weight, 0.0)
        self.assertLessEqual(rows[0].weight, 0.5)

    def test_marks_entries_that_produce_no_labels(self):
        with self._settings():
            label_feed_entries()

        self.non_matching.refresh_from_db()
        self.assertEqual(
            self.non_matching.classifier_model_fingerprint, self.fingerprint
        )
        self.assertEqual(
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry=self.non_matching
            ).count(),
            0,
        )

    def test_is_idempotent(self):
        with self._settings():
            first = label_feed_entries()
            second = label_feed_entries()

        self.assertGreater(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry=self.matching
            ).count(),
            1,
        )

    def test_skips_non_english_entries(self):
        with self._settings():
            label_feed_entries()

        self.french_entry.refresh_from_db()
        self.assertEqual(self.french_entry.classifier_model_fingerprint, "")

    def test_respects_db_limit(self):
        with self._settings():
            processed = label_feed_entries(db_limit=1)
        self.assertEqual(processed, 1)

    def test_unknown_label_text_is_skipped_not_raised(self):
        # "Ghost Label" is in the artifact but not in the database.
        with self._settings():
            label_feed_entries()
        self.assertFalse(ClassifierLabel.objects.filter(text="Ghost Label").exists())

    def test_expired_rows_reset_the_fingerprint_and_are_relabelled(self):
        with self._settings():
            label_feed_entries()

        ClassifierLabelFeedEntryCalculated.objects.filter(
            feed_entry=self.matching
        ).update(expires_at=timezone.now() - datetime.timedelta(days=1))

        with self._settings():
            label_feed_entries()

        # The entry must be re-labelled, not left permanently label-less.
        self.assertEqual(
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry=self.matching
            ).count(),
            1,
        )

    def test_new_model_fingerprint_reprocesses_entries(self):
        with self._settings():
            label_feed_entries()

        other_path = os.path.join(self.tmpdir.name, "classifier2.json")
        dump_artifact(
            other_path,
            labels=["Gaming"],
            vocabulary_terms=["nintendo"],
            idf=[1.0],
            coef=[20.0],
            intercept=[0.0],
            thresholds=[1.0],
            vectorizer=VectorizerConfig(**_VECTORIZER_KWARGS),
            taxonomy_fingerprint="sha256:test",
            training={},
        )

        with self._settings(CLASSIFIER_MODEL_PATH=other_path):
            processed = label_feed_entries()

        self.assertGreater(processed, 0)

    def test_missing_artifact_returns_zero_without_raising(self):
        missing_path = os.path.join(self.tmpdir.name, "does-not-exist.json")
        with self._settings(CLASSIFIER_MODEL_PATH=missing_path):
            processed = label_feed_entries()

        self.assertEqual(processed, 0)
        self.assertEqual(
            ClassifierLabelFeedEntryCalculated.objects.count(),
            0,
        )
        self.matching.refresh_from_db()
        self.assertEqual(self.matching.classifier_model_fingerprint, "")

    def test_corrupt_artifact_returns_zero_without_raising(self):
        """A disk-full write or interrupted rsync can leave `classifier.json`
        as non-JSON garbage. Regression for fix round 2: `load_artifact`
        used to let `json.JSONDecodeError` escape past `_get_artifact()`'s
        `(OSError, ArtifactError)` catch, so this would previously raise on
        every scheduled run instead of no-op-ing.
        """
        corrupt_path = os.path.join(self.tmpdir.name, "corrupt.json")
        with open(corrupt_path, "w") as f:
            f.write("{not valid json at all")

        with self._settings(CLASSIFIER_MODEL_PATH=corrupt_path):
            processed = label_feed_entries()

        self.assertEqual(processed, 0)
        self.assertEqual(ClassifierLabelFeedEntryCalculated.objects.count(), 0)
        self.matching.refresh_from_db()
        self.assertEqual(self.matching.classifier_model_fingerprint, "")

    def test_wrong_shape_artifact_returns_zero_without_raising(self):
        """Valid JSON but missing required keys (e.g. a write truncated
        partway through) must also no-op rather than raise. Regression for
        fix round 2: `load_artifact` used to let a raw `KeyError` (e.g.
        `KeyError: 'vectorizer'`) escape past `_get_artifact()`'s
        `(OSError, ArtifactError)` catch.
        """
        wrong_shape_path = os.path.join(self.tmpdir.name, "wrong_shape.json")
        with open(wrong_shape_path, "w") as f:
            json.dump({"format_version": 1}, f)

        with self._settings(CLASSIFIER_MODEL_PATH=wrong_shape_path):
            processed = label_feed_entries()

        self.assertEqual(processed, 0)
        self.assertEqual(ClassifierLabelFeedEntryCalculated.objects.count(), 0)
        self.matching.refresh_from_db()
        self.assertEqual(self.matching.classifier_model_fingerprint, "")
