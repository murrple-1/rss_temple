import logging

from django.db import transaction

from api.models import AlternateFeedURL, Feed

_logger = logging.getLogger("rss_temple")


def purge_duplicate_feed_urls() -> None:
    alternate_feed_url_count = 0
    with transaction.atomic():
        for feed_url in Feed.objects.values_list("feed_url", flat=True).iterator():
            _, deletes = AlternateFeedURL.objects.filter(
                feed_url__iexact=feed_url
            ).delete()
            alternate_feed_url_count += deletes.get("api.AlternateFeedURL", 0)

    _logger.info("removed %d alternate feed URLs", alternate_feed_url_count)
