import pprint
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import F

from api.models import FeedEntry


class Command(BaseCommand):
    help = "Remove duplicate feed entries"

    def handle(self, *args: Any, **options: Any) -> None:
        seen = set()
        to_remove = []
        for fe_dict in (
            FeedEntry.objects.order_by(F("updated_at").desc(nulls_last=True))
            .values("uuid", "feed_id", "url")
            .iterator()
        ):
            key = (fe_dict["feed_id"], fe_dict["url"])
            if key in seen:
                to_remove.append(fe_dict["uuid"])
            else:
                seen.add(key)

        count, model_count = FeedEntry.objects.filter(uuid__in=to_remove).delete()
        self.stderr.write(f"deleted {count} rows")
        self.stderr.write(pprint.pformat(model_count))
