import logging

from api.models import AlternateFeedURL, Feed

_logger = logging.getLogger("rss_temple")


def purge_duplicate_feed_urls() -> None:
    _, deletes = AlternateFeedURL.objects.filter(
        feed_url__in=Feed.objects.values("feed_url")
    ).delete()
    alternate_feed_url_count = deletes.get("api.AlternateFeedURL", 0)
    _logger.info("removed %d alternate feed URLs", alternate_feed_url_count)
