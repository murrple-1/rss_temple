import json
import os
import tempfile

from django.test import SimpleTestCase, TestCase

from api.text_classifier import lang_detector, prep_content


class LangDetectorTestCase(SimpleTestCase):
    def test_detect_iso639_3(self):
        self.assertEqual(
            lang_detector.detect_iso639_3(
                "This appears to be sufficient to test the detector"
            ),
            "ENG",
        )

        self.assertEqual(
            lang_detector.detect_iso639_3("a;'loi#$Asdf9vafklohjgaCV asdf89nh23r"),
            "UND",
        )


class PrepContentTestCase(SimpleTestCase):
    def test_prep_for_lang_detection(self):
        self.assertEqual(
            prep_content.prep_for_lang_detection("Test Title", "Test Content"),
            "Test Title Test Content",
        )

    def test_prep_for_classification(self):
        self.assertEqual(
            prep_content.prep_for_classification("Test Title", "Test Content"),
            "Test Title Test Content",
        )


class TaxonomyTestCase(TestCase):
    def test_has_exactly_the_expected_labels(self):
        from api.text_classifier.taxonomy import LABEL_NAMES, TAXONOMY

        self.assertEqual(len(TAXONOMY), 23)
        self.assertEqual(LABEL_NAMES, tuple(sorted(TAXONOMY)))

    def test_every_label_has_strong_terms(self):
        from api.text_classifier.taxonomy import TAXONOMY

        for name, terms in TAXONOMY.items():
            with self.subTest(label=name):
                self.assertGreaterEqual(len(terms.strong), 8, name)

    def test_terms_are_lowercase_and_stripped(self):
        from api.text_classifier.taxonomy import TAXONOMY

        for name, terms in TAXONOMY.items():
            for term in terms.strong | terms.weak | terms.exclude:
                with self.subTest(label=name, term=term):
                    self.assertEqual(term, term.lower().strip())
                    self.assertTrue(term)

    def test_no_term_is_both_strong_and_weak_for_one_label(self):
        from api.text_classifier.taxonomy import TAXONOMY

        for name, terms in TAXONOMY.items():
            with self.subTest(label=name):
                self.assertEqual(terms.strong & terms.weak, frozenset())

    def test_fingerprint_is_stable_and_prefixed(self):
        from api.text_classifier.taxonomy import taxonomy_fingerprint

        first = taxonomy_fingerprint()
        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(first, taxonomy_fingerprint())

    def test_module_does_not_import_django(self):
        import subprocess
        import sys

        # `django.conf.settings` is a lazy object: merely importing it (or
        # any module that does `from django.conf import settings`) raises
        # nothing on its own, only attribute access does. So asserting on
        # the subprocess's return code does not actually catch a Django
        # import -- it only catches imports that trigger the ORM/app
        # registry. Assert directly on sys.modules instead: after importing
        # the taxonomy module, no `django` module of any kind must be
        # loaded.
        script = (
            "import sys; import api.text_classifier.taxonomy; "
            "leaked = sorted(m for m in sys.modules "
            "if m == 'django' or m.startswith('django.')); "
            "assert not leaked, leaked"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            env={"PATH": "/usr/bin:/bin"},
            cwd=".",
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())


class SeedLabelerTestCase(TestCase):
    def test_single_strong_term_fires(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertIn("Gaming", label_text("A review of the new Nintendo handheld."))

    def test_single_weak_term_does_not_fire(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertNotIn("Gaming", label_text("The gameplay was fine."))

    def test_two_weak_terms_fire(self):
        from api.text_classifier.seed_labeler import label_text

        # NOTE: the brief's illustrative text used "console" as a second weak
        # term, but the taxonomy's fix rounds (Task 1) narrowed the Gaming
        # weak list to the bigram "gaming console" specifically because bare
        # "console" collides with the verb "to console" and console tables.
        # Adapted to two weak terms that are actually in the current
        # taxonomy: "gameplay" and "patch notes".
        self.assertIn(
            "Gaming",
            label_text("The gameplay improved a lot after the latest patch notes."),
        )

    def test_exclusion_vetoes_the_label(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertNotIn(
            "Gaming", label_text("Nintendo made a board game once, apparently.")
        )

    def test_matching_is_word_bounded(self):
        from api.text_classifier.seed_labeler import score_text

        # "ai" is not a term, but this guards the general principle: a term must
        # not match inside a longer word. "nba" must not match "unbalanced".
        self.assertEqual(score_text("The load was unbalanced.").get("Sport", 0), 0)

    def test_multi_word_phrases_match(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertIn("Movies & TV", label_text("It topped the box office again."))

    def test_multi_label(self):
        from api.text_classifier.seed_labeler import label_text

        labels = label_text("The soundtrack guitarist also scored the box office hit.")
        self.assertIn("Music", labels)
        self.assertIn("Movies & TV", labels)

    def test_empty_input_fires_nothing(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertEqual(label_text(""), frozenset())
        self.assertEqual(label_text("   "), frozenset())

    def test_distinct_terms_not_repeats(self):
        from api.text_classifier.seed_labeler import score_text

        # The same weak term ten times is still one distinct weak match.
        repeated = " ".join(["gameplay"] * 10)
        self.assertEqual(score_text(repeated).get("Gaming", 0), 1)

    def test_truncates_long_input(self):
        from api.text_classifier.seed_labeler import SEED_LABEL_MAX_CHARS, label_text

        padding = "x " * SEED_LABEL_MAX_CHARS
        self.assertNotIn("Gaming", label_text(padding + " nintendo"))

    def test_module_does_not_import_django(self):
        import subprocess
        import sys

        # Same rationale as taxonomy.py's equivalent test: this module is
        # imported by an off-box training script with no Django settings
        # configured, so no `django*` module may land in `sys.modules` as a
        # side effect of importing it. Assert on sys.modules directly rather
        # than the subprocess return code, since merely importing
        # `django.conf.settings` (a lazy object) raises nothing on its own.
        script = (
            "import sys; import api.text_classifier.seed_labeler; "
            "leaked = sorted(m for m in sys.modules "
            "if m == 'django' or m.startswith('django.')); "
            "assert not leaked, leaked"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            env={"PATH": "/usr/bin:/bin"},
            cwd=".",
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_reset_pattern_cache_picks_up_mutated_taxonomy(self):
        from api.text_classifier import taxonomy
        from api.text_classifier.seed_labeler import (
            label_text,
            reset_pattern_cache,
        )

        original_taxonomy = dict(taxonomy.TAXONOMY)

        def restore():
            taxonomy.TAXONOMY.clear()
            taxonomy.TAXONOMY.update(original_taxonomy)
            reset_pattern_cache()

        self.addCleanup(restore)

        # Warm the cache with the real taxonomy first, so the test actually
        # exercises invalidation rather than a cold first call.
        self.assertNotIn("Gaming", label_text("It smelled like petrichor."))

        taxonomy.TAXONOMY["Gaming"] = taxonomy.SeedTerms(
            strong=frozenset({"petrichor"})
        )
        reset_pattern_cache()

        self.assertIn("Gaming", label_text("It smelled like petrichor."))

    def test_longest_first_alternation_counts_distinct_terms_correctly(self):
        # Synthetic taxonomy entry, not the real one: today's taxonomy has no
        # strong-term pair where one is a prefix of the other, and it might
        # gain or lose one later, which would make this test either
        # vacuous or dependent on taxonomy content it shouldn't care about.
        #
        # "game" is a prefix of "game console"; both end on a word boundary
        # at the position where "game console" starts. Longest-first makes
        # the alternation try "game console" before "game" there, so
        # findall reports two distinct terms ("game", "game console") for
        # the two occurrences below, worth 2 strong matches (score 4).
        # Shortest-first would report only "game" for both occurrences (one
        # distinct term, score 2) because "game" wins the earlier branch.
        from api.text_classifier import taxonomy
        from api.text_classifier.seed_labeler import (
            reset_pattern_cache,
            score_text,
        )

        original_taxonomy = dict(taxonomy.TAXONOMY)

        def restore():
            taxonomy.TAXONOMY.clear()
            taxonomy.TAXONOMY.update(original_taxonomy)
            reset_pattern_cache()

        self.addCleanup(restore)

        taxonomy.TAXONOMY.clear()
        taxonomy.TAXONOMY["Synthetic"] = taxonomy.SeedTerms(
            strong=frozenset({"game", "game console"})
        )
        reset_pattern_cache()

        self.assertEqual(score_text("game console and game").get("Synthetic", 0), 4)


class SeedLabelerRegressionCorpusTestCase(TestCase):
    """False positives/negatives previously found by hand-building a matcher.

    Each case here was demonstrated against a real matcher during the two
    taxonomy fix rounds; this test suite is the first point at which they are
    asserted automatically. See api/text_classifier/taxonomy.py for the
    per-term commentary explaining why each of these is a collision.
    """

    def test_must_not_fire(self):
        from api.text_classifier.seed_labeler import label_text

        # (label that must NOT fire, text). Some of these texts legitimately
        # fire a *different* label -- that is correct and is not asserted
        # against here, only the absence of the named label is.
        cases = [
            (
                "Education",
                "It has, of course, been a learning experience for the "
                "whole team this season",
            ),
            (
                "Automobile & Vehicles",
                "The updated graphics driver boosts frame rates in "
                "Unreal Engine titles",
            ),
            (
                "Music",
                "Router review: single-band 2.4GHz Wi-Fi coverage for "
                "the whole house",
            ),
            (
                "Movies & TV",
                "The board cast the deciding vote to appoint a new director",
            ),
            (
                "Programming",
                "The property developer must follow the local building code",
            ),
            (
                "Sport",
                # Movies & TV firing here (via "sitcom") is correct.
                "The hit sitcom is returning with the same team for " "another season",
            ),
            (
                "Photography",
                "Investors have significant exposure to rate risk, viewed "
                "through the lens of recent Fed moves",
            ),
            (
                "Health",
                "The retreat blends wellness with traditional spa " "treatment rituals",
            ),
            (
                "Arts & Craft",
                # Food & Drink firing here (via "brewery") is correct.
                "This small-batch brewery makes everything handmade, true "
                "to the craft of brewing",
            ),
            (
                "Computer Hardware & Software",
                "Upgrade your suspension yourself — easy to install " "in an afternoon",
            ),
            (
                "Computer Hardware & Software",
                # Sport firing here (via "formula 1") is correct.
                "The Formula 1 driver praised the team's software update "
                "to the car's telemetry system",
            ),
            (
                "Photography",
                "The tech blog covered camera gear news, then explained "
                "how to download the ISO and flash it to a USB stick",
            ),
        ]
        for label, text in cases:
            with self.subTest(label=label, text=text):
                fired = label_text(text)
                self.assertNotIn(
                    label,
                    fired,
                    f"{label!r} incorrectly fired for {text!r}; "
                    f"labels fired: {sorted(fired)}",
                )

    def test_must_fire(self):
        from api.text_classifier.seed_labeler import label_text

        # Recall guard: confirms the fixes above did not overcorrect and
        # silence labels that should still fire on clearly on-topic text.
        cases = [
            (
                "Computer Hardware & Software",
                "We benchmarked the new graphics card against the previous "
                "generation using a synthetic gpu stress test.",
            ),
            (
                "Photography",
                "This lens review covers the new 85mm telephoto for "
                "mirrorless cameras, tested with a tripod.",
            ),
        ]
        for label, text in cases:
            with self.subTest(label=label, text=text):
                fired = label_text(text)
                self.assertIn(
                    label,
                    fired,
                    f"{label!r} failed to fire for {text!r}; "
                    f"labels fired: {sorted(fired)}",
                )

    def test_exclusion_vetoes_gaming(self):
        from api.text_classifier.seed_labeler import label_text

        cases = [
            "Fans debated the new board game expansion, praising its "
            "gameplay and multiplayer modes.",
            "The gaming commission opened an investigation into odds "
            "manipulation tied to several popular video games and esports "
            "betting platforms.",
        ]
        for text in cases:
            with self.subTest(text=text):
                fired = label_text(text)
                self.assertNotIn(
                    "Gaming",
                    fired,
                    f"Gaming incorrectly fired for {text!r}; "
                    f"labels fired: {sorted(fired)}",
                )


class ArtifactTestCase(TestCase):
    def _write(self, tmpdir, **overrides):
        from api.text_classifier.artifact import VectorizerConfig, dump_artifact

        kwargs = {
            "labels": ["Alpha", "Beta"],
            "vocabulary_terms": ["cat", "dog", "cat dog"],
            "idf": [1.0, 2.0, 3.0],
            "coef": [0.1, 0.2, 0.3, -0.1, -0.2, -0.3],
            "intercept": [0.5, -0.5],
            "thresholds": [0.0, 0.25],
            "vectorizer": VectorizerConfig(
                token_pattern=r"(?u)\b\w\w+\b",
                ngram_range=(1, 2),
                lowercase=True,
                sublinear_tf=True,
                norm="l2",
                stop_words=("the", "a"),
            ),
            "taxonomy_fingerprint": "sha256:deadbeef",
            "training": {"n_docs": 3},
        }
        kwargs.update(overrides)
        path = os.path.join(tmpdir, "artifact.json")
        fingerprint = dump_artifact(path, **kwargs)
        return path, fingerprint

    def test_round_trip(self):
        from api.text_classifier.artifact import load_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            path, fingerprint = self._write(tmpdir)
            artifact = load_artifact(path)

            self.assertEqual(artifact.labels, ("Alpha", "Beta"))
            self.assertEqual(artifact.vocabulary, {"cat": 0, "dog": 1, "cat dog": 2})
            self.assertEqual(list(artifact.idf), [1.0, 2.0, 3.0])
            self.assertEqual(len(artifact.coef), 6)
            self.assertAlmostEqual(artifact.coef[0], 0.1, places=6)
            self.assertAlmostEqual(artifact.coef[5], -0.3, places=6)
            self.assertEqual(list(artifact.intercept), [0.5, -0.5])
            self.assertEqual(artifact.model_fingerprint, fingerprint)
            self.assertEqual(artifact.taxonomy_fingerprint, "sha256:deadbeef")

    def test_fingerprint_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, first = self._write(tmpdir)
        with tempfile.TemporaryDirectory() as tmpdir:
            _, second = self._write(tmpdir)
        self.assertEqual(first, second)

    def test_fingerprint_changes_with_coefficients(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, first = self._write(tmpdir)
        with tempfile.TemporaryDirectory() as tmpdir:
            _, second = self._write(tmpdir, coef=[0.9, 0.2, 0.3, -0.1, -0.2, -0.3])
        self.assertNotEqual(first, second)

    def test_rejects_unsupported_format_version(self):
        from api.text_classifier.artifact import ArtifactError, load_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            path, _ = self._write(tmpdir)
            with open(path, "r") as f:
                raw = json.load(f)
            raw["format_version"] = 999
            with open(path, "w") as f:
                json.dump(raw, f)

            with self.assertRaises(ArtifactError):
                load_artifact(path)

    def test_rejects_unsupported_vectorizer_config(self):
        from api.text_classifier.artifact import ArtifactError, load_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            path, _ = self._write(tmpdir)
            with open(path, "r") as f:
                raw = json.load(f)
            raw["vectorizer"]["ngram_range"] = [1, 3]
            with open(path, "w") as f:
                json.dump(raw, f)

            with self.assertRaises(ArtifactError):
                load_artifact(path)

    def test_rejects_truncated_arrays(self):
        from api.text_classifier.artifact import ArtifactError, load_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            path, _ = self._write(tmpdir)
            with open(path, "r") as f:
                raw = json.load(f)
            raw["labels"] = ["Alpha", "Beta", "Gamma"]  # coef no longer 3 x 3
            with open(path, "w") as f:
                json.dump(raw, f)

            with self.assertRaises(ArtifactError):
                load_artifact(path)

    def test_rejects_vocabulary_term_containing_newline(self):
        from api.text_classifier.artifact import ArtifactError

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ArtifactError):
                self._write(tmpdir, vocabulary_terms=["cat", "dog\nbad", "cat dog"])

    def test_module_does_not_import_django(self):
        import subprocess
        import sys

        # Same rationale as taxonomy.py's and seed_labeler.py's equivalent
        # tests: this module is written by an off-box training script with
        # no Django installed at all, so no `django*` module may land in
        # sys.modules as a side effect of importing it. Assert on
        # sys.modules directly rather than the subprocess return code, since
        # merely importing `django.conf.settings` (a lazy object) raises
        # nothing on its own.
        script = (
            "import sys; import api.text_classifier.artifact; "
            "leaked = sorted(m for m in sys.modules "
            "if m == 'django' or m.startswith('django.')); "
            "assert not leaked, leaked"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            env={"PATH": "/usr/bin:/bin"},
            cwd=".",
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
