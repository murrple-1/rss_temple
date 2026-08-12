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

        result = subprocess.run(
            [sys.executable, "-c", "import api.text_classifier.taxonomy"],
            capture_output=True,
            env={"PATH": "/usr/bin:/bin"},
            cwd=".",
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
