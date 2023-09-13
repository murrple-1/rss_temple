from lingua import IsoCode639_3, Language, LanguageDetectorBuilder

_detector = LanguageDetectorBuilder.from_languages(
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
).build()


def detect_thresholded_iso639_3s(
    text: str, confidence_threshold: float
) -> dict[str, float]:
    detected_languages = detect_iso639_3s(text)
    remove_langs = [
        lang
        for lang, confidence in detected_languages.items()
        if confidence < confidence_threshold
    ]
    for lang in remove_langs:
        del detected_languages[lang]

    if not detected_languages:
        detected_languages["UND"] = 1.0

    new_confidence_sum = sum(detected_languages.values())
    return {
        lang: (confidence / new_confidence_sum)
        for lang, confidence in detected_languages.items()
    }


def detect_iso639_3s(text: str) -> dict[str, float]:
    confidence_values = _detector.compute_language_confidence_values(text)
    return {cv.language.iso_code_639_3.name: cv.value for cv in confidence_values}


def iso639_3_to_human_readable(iso639_3_str: str) -> str | None:
    iso639_3 = IsoCode639_3[iso639_3_str]
    language = Language.from_iso_code_639_3(iso639_3)
    return language.name
