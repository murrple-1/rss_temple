import logging
import datetime

from api.models import FeedEntry

_logger = logging.getLogger("rss_temple.tasks.ignore_missed_top_images")


def ignore_missed_top_images(epoch: datetime.datetime) -> None:
    count = FeedEntry.objects.filter(
        has_top_image_been_processed=False, db_created_at__lte=epoch
    ).update(has_top_image_been_processed=True, top_image_src="")

    _logger.info("updated %d feed entries", count)
