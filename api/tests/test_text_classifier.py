from django.test import SimpleTestCase

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
