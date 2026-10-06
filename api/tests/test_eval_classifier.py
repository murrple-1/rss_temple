"""Tests for `scripts/eval_classifier.py`.

`scripts/` is not a Django app and is not on `sys.path` as a package, so the
module is loaded directly from its file path rather than imported by dotted
name. This mirrors how the script is actually run (`python
scripts/eval_classifier.py`), and keeps these tests inside the Django test
runner (`manage.py test`) without needing pytest or a `scripts/__init__.py`.
"""

import contextlib
import importlib.util
import io
import json
import os
import tempfile
from types import ModuleType
from unittest import mock

from django.test import SimpleTestCase

_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "eval_classifier.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "eval_classifier_under_test", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrfTestCase(SimpleTestCase):
    """`prf` computes precision/recall/F1 from raw tp/fp/fn counts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mod = _load_module()

    def test_perfect_score(self):
        self.assertEqual(self.mod.prf(2, 0, 0), (1.0, 1.0, 1.0))

    def test_zero_tp_fp_fn_is_zero_not_a_crash(self):
        # No predictions, no gold truth for this label at all -- the
        # brief's required convention: 0.0/0.0/0.0, not ZeroDivisionError.
        self.assertEqual(self.mod.prf(0, 0, 0), (0.0, 0.0, 0.0))

    def test_false_positives_only_zero_precision(self):
        self.assertEqual(self.mod.prf(0, 3, 0), (0.0, 0.0, 0.0))

    def test_false_negatives_only_zero_recall(self):
        precision, recall, f1 = self.mod.prf(0, 0, 3)
        self.assertEqual((precision, recall, f1), (0.0, 0.0, 0.0))

    def test_partial_precision_and_recall(self):
        precision, recall, f1 = self.mod.prf(3, 1, 1)
        self.assertAlmostEqual(precision, 0.75)
        self.assertAlmostEqual(recall, 0.75)
        self.assertAlmostEqual(f1, 0.75)


class ScoreTestCase(SimpleTestCase):
    """`score` aggregates per-label counts across the whole gold set."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mod = _load_module()

    def test_per_label_counts_and_macro_and_coverage(self):
        from api.text_classifier.taxonomy import LABEL_NAMES

        gold_rows = [
            {"uuid": "a", "labels": ["Gaming"]},
            {"uuid": "b", "labels": ["Music"]},
            {"uuid": "c", "labels": []},
        ]
        predictions = {
            "a": {"Gaming"},  # true positive
            "b": set(),  # false negative for Music
            "c": {"Sport"},  # false positive for Sport
        }

        per_label, macro_f1, coverage = self.mod.score(predictions, gold_rows)

        self.assertEqual(set(per_label), set(LABEL_NAMES))
        self.assertEqual(per_label["Gaming"], (1.0, 1.0, 1.0))
        self.assertEqual(per_label["Music"], (0.0, 0.0, 0.0))
        self.assertEqual(per_label["Sport"], (0.0, 0.0, 0.0))
        # A label absent from both truth and every prediction across the
        # whole gold set is defined, not a crash.
        untouched = next(
            name for name in LABEL_NAMES if name not in ("Gaming", "Music", "Sport")
        )
        self.assertEqual(per_label[untouched], (0.0, 0.0, 0.0))

        expected_macro = sum(f for _, _, f in per_label.values()) / len(LABEL_NAMES)
        self.assertAlmostEqual(macro_f1, expected_macro)

        # rows "a" and "c" produced a non-empty prediction set; "b" did not.
        self.assertAlmostEqual(coverage, 2 / 3)

    def test_empty_gold_set_does_not_divide_by_zero(self):
        _, macro_f1, coverage = self.mod.score({}, [])
        self.assertEqual(coverage, 0.0)
        self.assertEqual(macro_f1, 0.0)

    def test_multi_label_row_scores_each_label_independently(self):
        gold_rows = [{"uuid": "a", "labels": ["Gaming", "Music"]}]
        predictions = {"a": {"Gaming"}}  # misses Music, no extra false positive

        per_label, _, _ = self.mod.score(predictions, gold_rows)
        self.assertEqual(per_label["Gaming"], (1.0, 1.0, 1.0))
        self.assertEqual(per_label["Music"], (0.0, 0.0, 0.0))  # fn=1


class BuildPredictionsTestCase(SimpleTestCase):
    """`build_predictions` must route every row through
    `prep_for_classification` -- the single truncation point in the whole
    pipeline -- rather than feeding raw title/content_excerpt straight to
    the model and the seed labeler.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mod = _load_module()

    def test_uses_prep_for_classification(self):
        gold_rows = [
            {
                "uuid": "a",
                "title": "T1",
                "content_excerpt": "C1",
                "feed_id": "f",
                "labels": [],
            },
            {
                "uuid": "b",
                "title": "T2",
                "content_excerpt": "C2",
                "feed_id": "f",
                "labels": [],
            },
        ]

        calls = []

        def fake_prep(title, content):
            calls.append((title, content))
            return f"prepped:{title}:{content}"

        seen_texts = []

        def fake_predict(artifact, text, max_labels):
            seen_texts.append(text)
            return []

        def fake_label_text(text):
            seen_texts.append(text)
            return frozenset()

        with (
            mock.patch.object(
                self.mod, "prep_for_classification", side_effect=fake_prep
            ),
            mock.patch.object(self.mod, "predict", side_effect=fake_predict),
            mock.patch.object(self.mod, "label_text", side_effect=fake_label_text),
        ):
            self.mod.build_predictions(
                artifact=object(), gold_rows=gold_rows, max_labels=3
            )

        self.assertEqual(calls, [("T1", "C1"), ("T2", "C2")])
        self.assertEqual(
            seen_texts,
            [
                "prepped:T1:C1",
                "prepped:T1:C1",
                "prepped:T2:C2",
                "prepped:T2:C2",
            ],
        )


class RunTestCase(SimpleTestCase):
    """End-to-end behaviour of `run`, including both ship gates.

    Uses small, hand-built artifacts (via `dump_artifact`) rather than a
    real trained model, so these are hermetic and do not depend on any
    committed classifier.json.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mod = _load_module()

    def _write_artifact(self, tmpdir, feature_term="nintendo", **overrides):
        from api.text_classifier.artifact import VectorizerConfig, dump_artifact
        from api.text_classifier.taxonomy import LABEL_NAMES, taxonomy_fingerprint

        # A single-feature artifact that fires "Gaming" whenever
        # `feature_term` appears, and nothing else -- enough to construct
        # gold sets where the model is right, wrong, or silent in
        # controlled ways.
        labels = list(LABEL_NAMES)
        gaming_index = labels.index("Gaming")
        n_labels = len(labels)

        coef = [0.0] * n_labels
        coef[gaming_index] = 10.0
        intercept = [-5.0] * n_labels
        thresholds = [0.0] * n_labels

        kwargs = dict(
            labels=labels,
            vocabulary_terms=[feature_term],
            idf=[1.0],
            coef=coef,
            intercept=intercept,
            thresholds=thresholds,
            vectorizer=VectorizerConfig(
                token_pattern=r"(?u)\b\w\w+\b",
                ngram_range=(1, 2),
                lowercase=True,
                sublinear_tf=True,
                norm="l2",
                stop_words=(),
                binary=False,
                strip_accents=None,
                analyzer="word",
            ),
            taxonomy_fingerprint=taxonomy_fingerprint(),
            training={},
        )
        kwargs.update(overrides)
        path = os.path.join(tmpdir, "artifact.json")
        dump_artifact(path, **kwargs)
        return path

    def _write_gold(self, tmpdir, rows):
        path = os.path.join(tmpdir, "gold.jsonl")
        with open(path, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        return path

    def _args(self, artifact_path, gold_path, **overrides):
        import argparse

        defaults = dict(
            artifact=artifact_path,
            gold=gold_path,
            max_labels=3,
            precision_floor=0.5,
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_both_gates_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # "gameplay" is only a *weak* Gaming term in the real taxonomy
            # (see taxonomy.py); one mention scores 1, below the seed
            # labeler's threshold of 2, so the raw seed matcher misses
            # every row below -- confirmed directly against `score_text`
            # while writing this test. The hand-built model keys on that
            # same word directly, with no threshold problem, so it beats
            # the seed labeler on this gold set (gate 1) while every
            # prediction it makes is also correct (gate 2).
            artifact_path = self._write_artifact(tmpdir, feature_term="gameplay")
            rows = [
                {
                    "uuid": str(i),
                    "title": "Review",
                    "content_excerpt": "The gameplay improved this year.",
                    "feed_id": "f",
                    "labels": ["Gaming"],
                }
                for i in range(5)
            ]
            gold_path = self._write_gold(tmpdir, rows)

            out = io.StringIO()
            err = io.StringIO()
            code = self.mod.run(self._args(artifact_path, gold_path), out=out, err=err)

            self.assertEqual(code, 0)
            self.assertIn("GATE 1", out.getvalue())
            self.assertIn("PASS", out.getvalue())
            self.assertNotIn("BELOW PRECISION FLOOR", out.getvalue())

    def test_gate_1_fails_when_model_does_not_beat_seed_labeler(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Force the model to never fire (impossibly high threshold),
            # while the gold text has two strong Gaming terms so the raw
            # seed labeler beats it outright.
            artifact_path = self._write_artifact(
                tmpdir, thresholds=[1000.0] * len(self.mod.LABEL_NAMES)
            )
            rows = [
                {
                    "uuid": str(i),
                    "title": "Review",
                    "content_excerpt": "Nintendo esports coverage this week.",
                    "feed_id": "f",
                    "labels": ["Gaming"],
                }
                for i in range(5)
            ]
            gold_path = self._write_gold(tmpdir, rows)

            out = io.StringIO()
            code = self.mod.run(
                self._args(artifact_path, gold_path), out=out, err=io.StringIO()
            )

            self.assertEqual(code, 1)
            self.assertIn("GATE 1", out.getvalue())
            self.assertIn("FAIL", out.getvalue())

    def test_gate_2_fails_when_a_label_precision_is_below_floor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = self._write_artifact(tmpdir)
            # The model fires Gaming on every row (see the artifact above),
            # but only some rows are truly Gaming in the gold set -- enough
            # false positives to push Gaming's precision under the floor.
            rows = [
                {
                    "uuid": "1",
                    "title": "Review",
                    "content_excerpt": "Nintendo handheld news.",
                    "feed_id": "f",
                    "labels": ["Gaming"],
                },
                {
                    "uuid": "2",
                    "title": "Unrelated",
                    "content_excerpt": "Nintendo brand mentioned in passing.",
                    "feed_id": "f",
                    "labels": [],
                },
                {
                    "uuid": "3",
                    "title": "Unrelated",
                    "content_excerpt": "Nintendo brand mentioned in passing again.",
                    "feed_id": "f",
                    "labels": [],
                },
            ]
            gold_path = self._write_gold(tmpdir, rows)

            out = io.StringIO()
            code = self.mod.run(
                self._args(artifact_path, gold_path), out=out, err=io.StringIO()
            )

            self.assertEqual(code, 1)
            self.assertIn("GATE 2", out.getvalue())
            self.assertIn("FAIL", out.getvalue())
            self.assertIn("Gaming", out.getvalue())
            self.assertIn("BELOW PRECISION FLOOR", out.getvalue())

    def test_gate_2_passes_when_all_predicted_labels_meet_the_floor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Same "gameplay" setup as test_both_gates_pass above: the raw
            # seed matcher does not reach its threshold on this text (one
            # weak-term mention scores 1, needs 2), so gate 1 also passes
            # here -- this test's focus is specifically that gate 2 passes
            # when the model's only predicted label has perfect precision.
            artifact_path = self._write_artifact(tmpdir, feature_term="gameplay")
            rows = [
                {
                    "uuid": str(i),
                    "title": "Review",
                    "content_excerpt": "The gameplay improved this year.",
                    "feed_id": "f",
                    "labels": ["Gaming"],
                }
                for i in range(5)
            ]
            gold_path = self._write_gold(tmpdir, rows)

            out = io.StringIO()
            code = self.mod.run(
                self._args(artifact_path, gold_path), out=out, err=io.StringIO()
            )

            self.assertEqual(code, 0)
            self.assertIn("GATE 2", out.getvalue())
            self.assertIn("PASS", out.getvalue())

    def test_missing_gold_file_is_a_usage_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = self._write_artifact(tmpdir)
            missing = os.path.join(tmpdir, "does_not_exist.jsonl")

            err = io.StringIO()
            code = self.mod.run(
                self._args(artifact_path, missing), out=io.StringIO(), err=err
            )
            self.assertEqual(code, 2)
            self.assertIn("does_not_exist.jsonl", err.getvalue())

    def test_missing_artifact_is_a_usage_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gold_path = self._write_gold(tmpdir, [])
            missing = os.path.join(tmpdir, "does_not_exist.json")

            err = io.StringIO()
            code = self.mod.run(
                self._args(missing, gold_path), out=io.StringIO(), err=err
            )
            self.assertEqual(code, 2)

    def test_empty_gold_set_is_a_usage_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = self._write_artifact(tmpdir)
            gold_path = self._write_gold(tmpdir, [])

            err = io.StringIO()
            code = self.mod.run(
                self._args(artifact_path, gold_path), out=io.StringIO(), err=err
            )
            self.assertEqual(code, 2)

    def test_warns_on_taxonomy_fingerprint_drift(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = self._write_artifact(
                tmpdir, taxonomy_fingerprint="sha256:stale"
            )
            gold_path = self._write_gold(tmpdir, [])

            err = io.StringIO()
            self.mod.run(
                self._args(artifact_path, gold_path), out=io.StringIO(), err=err
            )
            self.assertIn("taxonomy_fingerprint", err.getvalue())


class MainSmokeTestCase(SimpleTestCase):
    """Argument parsing and the sys.exit contract, exercised without
    actually invoking a subprocess.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mod = _load_module()

    def test_main_exits_with_runs_return_code(self):
        with mock.patch.object(self.mod, "run", return_value=7) as mock_run:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    with mock.patch("sys.argv", ["eval_classifier.py"]):
                        self.mod.main()
            self.assertEqual(cm.exception.code, 7)
            mock_run.assert_called_once()

    def test_default_paths(self):
        with mock.patch("sys.argv", ["eval_classifier.py"]):
            args = self.mod.build_arg_parser().parse_args()
        self.assertEqual(args.artifact, "api/text_classifier/model/classifier.json")
        self.assertEqual(args.gold, "api/text_classifier/gold/gold_set.jsonl")
        self.assertEqual(args.max_labels, 3)
        self.assertEqual(args.precision_floor, 0.5)
