from typing import Any

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from lingua import Language, LanguageDetector, LanguageDetectorBuilder

_detector: LanguageDetector


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _detector

    _detector = _detector = (
        LanguageDetectorBuilder.from_languages(
            # based on https://www.isocfoundation.org/2023/05/what-are-the-most-used-languages-on-the-internet/
            Language.ENGLISH,
            Language.SPANISH,
            Language.RUSSIAN,
            Language.GERMAN,
            Language.FRENCH,
            Language.JAPANESE,
            Language.PORTUGUESE,
            Language.TURKISH,
            Language.ITALIAN,
            Language.PERSIAN,
            Language.DUTCH,
            Language.CHINESE,
            # additional known
            Language.ROMANIAN,
            # TODO which languages to support? maybe all?
        )
        .with_minimum_relative_distance(settings.LINGUA_MINIMUM_RELATIVE_DISTANCE)
        .build()
    )


_load_global_settings()


def detect_iso639_3(text: str) -> str:
    detected_language = _detector.detect_language_of(text)
    if detected_language is None:
        return "UND"  # from https://en.wikipedia.org/wiki/ISO_639-3#Special_codes
    else:
        return detected_language.iso_code_639_3.name
