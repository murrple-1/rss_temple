import logging

from django.core.management.base import BaseCommand

from api.models import ReadFeedEntryUserMapping

_logger = logging.getLogger("rss_temple")


class Command(BaseCommand):
    help = "TODO help text"

    def handle(self, *args, **options):
        count, _ = ReadFeedEntryUserMapping.objects.all().delete()
        _logger.info("%d read entries removed", count)
