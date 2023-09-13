from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import FeedEntry, Language
from api.text_classifier.lang_detector import detect_iso639_3
from api.text_classifier.prep_content import prep_for_lang_detection


class Command(BaseCommand):
    help = "Rerun language detection of the feed entry content"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--show-detected-lang", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        verbosity = options["verbosity"]
        dry_run = options["dry_run"]
        show_detected_lang = options["show_detected_lang"]

        language_dict: dict[str, Language] = {
            l.iso639_3: l for l in Language.objects.all()
        }

        qs = FeedEntry.objects.filter(language__isnull=True)
        total = qs.count()

        try:
            for i, feed_entry in enumerate(qs.order_by("-published_at").iterator()):
                content = prep_for_lang_detection(feed_entry.content)
                detected_language = detect_iso639_3(content)

                if not dry_run:
                    feed_entry.language = language_dict[detected_language]
                    feed_entry.save(update_fields=("language",))

                if verbosity >= 2:
                    self.stderr.write(self.style.NOTICE(f"{i + 1}/{total}"))

                if show_detected_lang:
                    self.stderr.write(
                        self.style.SUCCESS(
                            f"{detected_language}: {language_dict[detected_language].name}"
                        )
                    )
        except KeyboardInterrupt:
            pass
