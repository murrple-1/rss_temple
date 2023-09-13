import pprint
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from api.models import FeedEntry, FeedEntryLanguageMapping
from api.text_classifier.lang_detector import (
    detect_thresholded_iso639_3s,
    iso639_3_to_human_readable,
)
from api.text_classifier.prep_content import prep_for_lang_detection


class Command(BaseCommand):
    help = "Rerun language detection of the feed entry content"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--lingua-confidence-threshold",
            type=float,
            default=settings.LINGUA_CONFIDENCE_THRESHOLD,
        )
        parser.add_argument("--max-langs", type=int)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--show-detected-langs", action="store_true")
        parser.add_argument("--show-multi-langs", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        verbosity = options["verbosity"]
        dry_run = options["dry_run"]
        lingua_confidence_threshold = options["lingua_confidence_threshold"]
        show_detected_langs = options["show_detected_langs"]
        show_multi_langs = options["show_multi_langs"]
        max_langs = options["max_langs"]

        qs = FeedEntry.objects.exclude(
            uuid__in=FeedEntryLanguageMapping.objects.values("feed_entry_id")
        )
        total = qs.count()

        try:
            for i, feed_entry in enumerate(qs.order_by("-published_at").iterator()):
                content = prep_for_lang_detection(feed_entry.content)
                detected_languages = detect_thresholded_iso639_3s(
                    content, lingua_confidence_threshold
                )

                if max_langs is not None and len(detected_languages) > max_langs:
                    readable_langs = {
                        lang: (confidence, iso639_3_to_human_readable(lang))
                        for lang, confidence in detected_languages.items()
                    }
                    raise CommandError(
                        f"too many langs:\n{content}\n{pprint.pformat(readable_langs)}"
                    )

                if not dry_run:
                    with transaction.atomic():
                        FeedEntryLanguageMapping.objects.filter(
                            feed_entry=feed_entry
                        ).delete()
                        FeedEntryLanguageMapping.objects.bulk_create(
                            FeedEntryLanguageMapping(
                                language_id=lang,
                                feed_entry=feed_entry,
                                confidence=confidence,
                            )
                            for lang, confidence in detected_languages.items()
                        )

                if verbosity >= 2:
                    self.stderr.write(self.style.NOTICE(f"{i + 1}/{total}"))

                if show_detected_langs:
                    readable_langs = {
                        lang: (confidence, iso639_3_to_human_readable(lang))
                        for lang, confidence in detected_languages.items()
                    }
                    self.stderr.write(
                        self.style.SUCCESS(pprint.pformat(readable_langs))
                    )
                if show_multi_langs and len(detected_languages) > 1:
                    self.stderr.write(self.style.WARNING(content))
        except KeyboardInterrupt:
            pass
