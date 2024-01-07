import uuid
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from api import content_type_util, rss_requests
from api.models import Feed
from api.requests_extensions import safe_response_text
from api.tasks import feed_scrape


class Command(BaseCommand):
    help = "Web-scrape the various feeds and update our DB"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("-c", "--count", type=int, default=1000)
        parser.add_argument("--feed-url")
        parser.add_argument("--feed-uuid")

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover
        feed: Feed
        if feed_url := options["feed_url"]:
            feed = Feed.objects.get(feed_url=feed_url)
        elif feed_uuid := options["feed_uuid"]:
            feed = Feed.objects.get(uuid=uuid.UUID(feed_uuid))
        else:
            raise CommandError("either --feed-url or --feed-uuid must be specified")

        response = rss_requests.get(feed.feed_url, stream=True)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type")
        if content_type is not None and not content_type_util.is_feed(content_type):
            raise ValueError(f"bad content type: {content_type}")
        response_text = safe_response_text(response, settings.DOWNLOAD_MAX_BYTE_COUNT)
        with transaction.atomic():
            feed_scrape(feed, response_text)
            feed.save(update_fields=["db_updated_at"])
