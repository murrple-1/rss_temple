import json
import math
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
                binary=False,
                strip_accents=None,
                analyzer="word",
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

        # Every field `load_artifact` actually validates against a fixed
        # supported value. `stop_words` is deliberately absent: it is
        # training-determined data with no single "supported" value, unlike
        # the other eight. A prior review flagged that this test only
        # exercised `ngram_range`, leaving seven of the eight fields'
        # rejection guards unverified -- each other field could have had a
        # broken or missing check and this test would still have passed.
        cases = [
            ("token_pattern", r"\w+"),
            ("ngram_range", [1, 3]),
            ("norm", "l1"),
            ("lowercase", False),
            ("sublinear_tf", False),
            ("binary", True),
            ("strip_accents", "unicode"),
            ("analyzer", "char"),
        ]
        for field, bad_value in cases:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as tmpdir:
                    path, _ = self._write(tmpdir)
                    with open(path, "r") as f:
                        raw = json.load(f)
                    raw["vectorizer"][field] = bad_value
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


class ImportGuardTestCase(TestCase):
    def test_views_do_not_import_the_classifier(self):
        """The model must live in the dramatiq worker, not in every web worker.

        `api.views` is imported by every one of `cpu_count() * 2 + 1` gunicorn
        workers. A transitive import of `classifier` here would load the ~10MB
        artifact into each of them, silently.
        """
        import subprocess
        import sys

        script = (
            "import os, django;"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rss_temple.settings');"
            "django.setup();"
            "import api.views;"
            "import sys;"
            "assert 'api.text_classifier.classifier' not in sys.modules, "
            "'api.views transitively imports api.text_classifier.classifier'"
        )
        result = subprocess.run([sys.executable, "-c", script], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())


class ParityTestCase(TestCase):
    """Checks the pure-Python inference path against scikit-learn's own scores.

    There is deliberately no production `classifier.json` committed to this
    repository: the only corpus available when this was written is
    synthetic (seeded from `taxonomy.py`, not real feed content), and
    shipping a synthetic-data model as the real classifier.json would give
    every self-hoster a worthless model with no visible warning. The real
    artifact gets trained from production data later, via
    `scripts/train_classifier.py`, and committed then.

    That leaves this test with nothing to compare against unless something
    is committed now. So `parity_artifact.json` / `parity_fixtures.json` are
    a second, deliberately small pair of files: the same training script,
    the same synthetic corpus, trained with a small `--max-features` purely
    so this test has a real trained artifact and real sklearn-computed
    scores to check the pure-Python path against. It is not a candidate
    classifier -- see the module docstring above and README.md's "Training
    the classifier" section. Once a real `classifier.json` exists, this test
    can point at it if that becomes more convenient, but must not go back to
    silently skipping in the meantime.
    """

    ARTIFACT = "api/text_classifier/model/parity_artifact.json"
    FIXTURES = "api/text_classifier/model/parity_fixtures.json"

    def test_pure_python_matches_sklearn(self):
        if not (os.path.exists(self.ARTIFACT) and os.path.exists(self.FIXTURES)):
            self.skipTest("no trained artifact; run scripts/train_classifier.py")

        from api.text_classifier.artifact import load_artifact
        from api.text_classifier.classifier import decision_scores

        artifact = load_artifact(self.ARTIFACT)
        with open(self.FIXTURES, "r") as f:
            fixtures = json.load(f)

        self.assertGreaterEqual(len(fixtures), 10)

        for fixture in fixtures:
            with self.subTest(text=fixture["text"][:40]):
                actual = decision_scores(artifact, fixture["text"])
                self.assertEqual(len(actual), len(fixture["scores"]))
                for label, expected_score, actual_score in zip(
                    artifact.labels, fixture["scores"], actual
                ):
                    # Relative, not fixed-decimal-places: the artifact
                    # stores float32 while sklearn computes float64, with a
                    # measured worst case of ~1.9e-6 relative over many
                    # random models. `places=4` (5e-5 absolute) happens to
                    # clear that for this small synthetic model (|score| <
                    # 1.5), but a real model with |score| in the 10-20 range
                    # would need ~2.5e-6-5e-6 *relative* precision to pass
                    # `places=4` -- tighter than the ~1e-5 relative floor
                    # this test is allowed to enforce, and only ~1.3x above
                    # the measured float32 noise floor. A relative
                    # comparison keeps the tolerance meaningful regardless
                    # of the trained model's score magnitude. `abs_tol`
                    # exists only so a fixture whose expected score is near
                    # zero doesn't require literally exact equality.
                    self.assertTrue(
                        math.isclose(
                            actual_score, expected_score, rel_tol=1e-5, abs_tol=1e-5
                        ),
                        f"{label}: actual={actual_score!r} "
                        f"expected={expected_score!r} "
                        f"diff={abs(actual_score - expected_score):.3e}",
                    )

    def test_artifact_matches_current_taxonomy(self):
        if not os.path.exists(self.ARTIFACT):
            self.skipTest("no trained artifact")

        from api.text_classifier.artifact import load_artifact
        from api.text_classifier.taxonomy import taxonomy_fingerprint

        artifact = load_artifact(self.ARTIFACT)
        self.assertEqual(
            artifact.taxonomy_fingerprint,
            taxonomy_fingerprint(),
            "seed terms have changed since this model was trained; retrain",
        )


class ClassifierInferenceTestCase(TestCase):
    def _artifact(self):
        """A hand-built two-label, three-feature artifact with known answers."""
        from api.text_classifier.artifact import (
            VectorizerConfig,
            dump_artifact,
            load_artifact,
        )

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        path = os.path.join(self.tmpdir.name, "artifact.json")
        dump_artifact(
            path,
            labels=["Alpha", "Beta"],
            vocabulary_terms=["cat", "dog", "cat dog"],
            idf=[1.0, 1.0, 1.0],
            # Alpha keys on "cat", Beta keys on "dog"
            coef=[10.0, 0.0, 0.0, 0.0, 10.0, 0.0],
            intercept=[0.0, 0.0],
            thresholds=[1.0, 1.0],
            vectorizer=VectorizerConfig(
                token_pattern=r"(?u)\b\w\w+\b",
                ngram_range=(1, 2),
                lowercase=True,
                sublinear_tf=True,
                norm="l2",
                stop_words=("the",),
                binary=False,
                strip_accents=None,
                analyzer="word",
            ),
            taxonomy_fingerprint="sha256:test",
            training={},
        )
        return load_artifact(path)

    def test_analyze_removes_stop_words_before_bigrams(self):
        from api.text_classifier.artifact import VectorizerConfig
        from api.text_classifier.classifier import analyze

        config = VectorizerConfig(
            token_pattern=r"(?u)\b\w\w+\b",
            ngram_range=(1, 2),
            lowercase=True,
            sublinear_tf=True,
            norm="l2",
            stop_words=("the",),
            binary=False,
            strip_accents=None,
            analyzer="word",
        )
        terms = analyze("the cat dog", config)
        self.assertEqual(terms, ["cat", "dog", "cat dog"])
        self.assertNotIn("the cat", terms)

    def test_analyze_drops_single_character_tokens(self):
        from api.text_classifier.artifact import VectorizerConfig
        from api.text_classifier.classifier import analyze

        config = VectorizerConfig(
            token_pattern=r"(?u)\b\w\w+\b",
            ngram_range=(1, 2),
            lowercase=True,
            sublinear_tf=True,
            norm="l2",
            stop_words=(),
            binary=False,
            strip_accents=None,
            analyzer="word",
        )
        self.assertEqual(analyze("a cat", config), ["cat"])

    def test_lowercase_happens_before_tokenizing(self):
        from api.text_classifier.artifact import VectorizerConfig
        from api.text_classifier.classifier import analyze

        config = VectorizerConfig(
            token_pattern=r"(?u)\b\w\w+\b",
            ngram_range=(1, 2),
            lowercase=True,
            sublinear_tf=True,
            norm="l2",
            stop_words=(),
            binary=False,
            strip_accents=None,
            analyzer="word",
        )
        # U+0130 (LATIN CAPITAL LETTER I WITH DOT ABOVE, "İ") lowercases in
        # Python to "i" followed by a combining dot above (U+0307), which
        # is not a \w character. Lowercasing the whole document *before*
        # tokenizing -- what sklearn does, and what this must match --
        # therefore splits "İstanbul" into a lone "i" (dropped: shorter
        # than \w\w+) and "stanbul". Tokenizing the *original* text first
        # and lowercasing each token afterward instead sees "İstanbul" as
        # one Unicode word character run and produces a single un-split
        # token, "i̇stanbul", once lowercased. Verified directly against
        # this Python's str.lower() and re before writing this assertion.
        self.assertEqual(analyze("İstanbul", config), ["stanbul"])

    def test_l2_normalisation_makes_length_irrelevant(self):
        from api.text_classifier.classifier import decision_scores

        artifact = self._artifact()
        short = decision_scores(artifact, "cat")
        long = decision_scores(artifact, "cat " * 20)
        # Repeating one term must not change the unit vector's direction.
        self.assertAlmostEqual(short[0], long[0], places=5)

    def test_sublinear_tf_uses_natural_log_not_log10(self):
        """Pins the exact decision score for a multi-feature vector.

        `test_l2_normalisation_makes_length_irrelevant` above only exercises
        a document with a single active feature. After L2 normalisation, a
        vector with exactly one non-zero component always normalises to
        1.0 regardless of what the raw tf value was (norm == |value|), so
        that test cannot distinguish `1 + ln(count)` from `1 + log10(count)`
        -- both give the same normalised result whenever every active term
        has count 1. This test uses "cat cat dog", which puts unequal counts
        (cat: 2, dog: 1, "cat dog": 1) into three *different* features at
        once, so the ratio between components -- and therefore the
        direction of the normalised vector -- depends on the log base used
        for sublinear tf. The expected value is computed here from `math.log`
        (natural log, matching scikit-learn's TfidfTransformer) independently
        of the implementation under test.
        """
        from api.text_classifier.classifier import decision_scores

        artifact = self._artifact()
        scores = decision_scores(artifact, "cat cat dog")

        tf_cat = 1.0 + math.log(2)
        tf_dog = 1.0 + math.log(1)
        tf_bigram = 1.0 + math.log(1)  # "cat dog" bigram occurs once
        norm = math.sqrt(tf_cat**2 + tf_dog**2 + tf_bigram**2)
        expected_alpha = 10.0 * (tf_cat / norm)  # Alpha's coef is 10 on "cat"

        self.assertAlmostEqual(scores[0], expected_alpha, places=5)

    def test_idf_multiplies_before_l2_normalisation(self):
        """Pins tf -> idf -> normalise ordering using non-uniform idf.

        `self._artifact()`'s idf is uniform ([1.0, 1.0, 1.0]), which makes
        the two possible orderings indistinguishable: scaling every
        component by the same idf before taking the L2 norm is equivalent
        (up to that shared scale factor) to scaling the already-unit
        vector by it afterward, when idf is a single repeated value. This
        artifact uses three distinct idf values instead, so the orderings
        diverge and this test can tell them apart.
        """
        from api.text_classifier.artifact import (
            VectorizerConfig,
            dump_artifact,
            load_artifact,
        )
        from api.text_classifier.classifier import decision_scores

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "artifact.json")
            dump_artifact(
                path,
                labels=["Alpha"],
                vocabulary_terms=["cat", "dog", "cat dog"],
                idf=[1.0, 2.5, 4.0],
                coef=[10.0, 0.0, 0.0],  # Alpha keys on "cat" only
                intercept=[0.0],
                thresholds=[0.0],
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
                taxonomy_fingerprint="sha256:test",
                training={},
            )
            artifact = load_artifact(path)

        scores = decision_scores(artifact, "cat dog")

        # "cat dog" produces cat, dog, and the "cat dog" bigram, each with
        # count 1, so sublinear tf is 1 + ln(1) == 1.0 for all three --
        # uniform tf isolates the idf x normalise ordering as the only
        # thing that can make this diverge from the correct implementation.
        tf = 1.0
        idf = [1.0, 2.5, 4.0]
        values = [tf * w for w in idf]
        norm = math.sqrt(sum(v * v for v in values))
        expected = 10.0 * (values[0] / norm)

        self.assertAlmostEqual(scores[0], expected, places=5)

    def test_predict_returns_only_labels_over_threshold(self):
        from api.text_classifier.classifier import predict

        artifact = self._artifact()
        predictions = predict(artifact, "cat", max_labels=3)
        self.assertEqual([p.label for p in predictions], ["Alpha"])

    def test_predict_orders_by_score_and_truncates(self):
        from api.text_classifier.classifier import predict

        artifact = self._artifact()
        predictions = predict(artifact, "cat dog", max_labels=1)
        self.assertEqual(len(predictions), 1)

    def test_predict_with_negative_max_labels_returns_nothing(self):
        from api.text_classifier.classifier import predict

        artifact = self._artifact()
        # `predictions[:-1]` would silently drop only the last prediction
        # instead of returning nothing; max_labels must clamp to zero.
        self.assertEqual(predict(artifact, "cat dog", max_labels=-1), [])

    def test_probability_is_between_zero_and_one(self):
        from api.text_classifier.classifier import predict

        artifact = self._artifact()
        for prediction in predict(artifact, "cat dog", max_labels=3):
            self.assertGreater(prediction.probability, 0.0)
            self.assertLess(prediction.probability, 1.0)

    def test_sigmoid_does_not_overflow(self):
        from api.text_classifier.classifier import sigmoid

        self.assertAlmostEqual(sigmoid(-10000.0), 0.0)
        self.assertAlmostEqual(sigmoid(10000.0), 1.0)

    def test_empty_and_out_of_vocabulary_text_scores_the_intercept(self):
        from api.text_classifier.classifier import decision_scores

        artifact = self._artifact()
        self.assertEqual(decision_scores(artifact, ""), [0.0, 0.0])
        self.assertEqual(decision_scores(artifact, "zebra"), [0.0, 0.0])

    def test_module_does_not_import_django(self):
        import subprocess
        import sys

        # Same rationale as the other text_classifier modules' equivalent
        # tests: classifier.py is loaded lazily inside the dramatiq task so
        # the model lives in exactly one process, and must not pull Django
        # into that process as a side effect of import. Assert on
        # sys.modules directly rather than the subprocess return code, since
        # merely importing `django.conf.settings` (a lazy object) raises
        # nothing on its own.
        script = (
            "import sys; import api.text_classifier.classifier; "
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
