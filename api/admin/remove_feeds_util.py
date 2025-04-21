from typing import Any
import uuid
from collections import defaultdict

from django.db.models import QuerySet
from django.forms import BaseFormSet
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import render as render_
from django.db import transaction

from api.forms import RemoveFeedsFormset
from api.models import Feed, AlternateFeedURL, FeedEntryReport, FeedReport, RemovedFeed


def remove_feeds(feed_id_to_reason_mapping: dict[uuid.UUID, str]) -> None:
    feeds = {
        f.uuid: f
        for f in Feed.objects.filter(uuid__in=feed_id_to_reason_mapping.values())
    }

    alternate_feed_urls: dict[str, list[AlternateFeedURL]] = defaultdict(list)
    for alternate_feed_url in AlternateFeedURL.objects.filter(
        feed_id__in=feed_id_to_reason_mapping.values()
    ):
        alternate_feed_urls[alternate_feed_url.feed.feed_url].append(alternate_feed_url)

    remove_urls_and_reasons: dict[str, tuple[str, str]] = {}
    for feed_id, reason in feed_id_to_reason_mapping.items():
        feed = feeds[feed_id]

        remove_urls_and_reasons[feed.feed_url] = (feed.feed_url, reason)

        for alternate_feed_url in alternate_feed_urls[feed.feed_url]:
            remove_urls_and_reasons[alternate_feed_url.feed_url] = (
                alternate_feed_url.feed_url,
                f"duplicate of {feed.feed_url}\n---\n{reason}",
            )

    with transaction.atomic():
        Feed.objects.filter(feed_url__in=remove_urls_and_reasons.keys()).delete()
        RemovedFeed.objects.bulk_create(
            (
                RemovedFeed(feed_url=url, reason=reason)
                for url, reason in remove_urls_and_reasons.values()
            ),
            batch_size=1024,
            ignore_conflicts=True,
        )


def render(
    request: HttpRequest, formset: BaseFormSet, selection_action_ids: list[str]
) -> HttpResponse:
    return render_(
        request,
        "admin/remove_feeds.html",
        {
            "title": "Remove Feeds",
            "formset": formset,
            "selected_action_ids": selection_action_ids,
        },
    )


def generate_formset(queryset: QuerySet[Feed], query_post: QueryDict | None = None):
    initial: list[dict[str, Any]] = []

    for feed in queryset:
        known_reasons: set[str] = set()

        known_reasons.update(
            FeedEntryReport.objects.filter(feed_entry__feed=feed)
            .exclude(reason="")
            .values_list("reason", flat=True)
        )
        known_reasons.update(
            FeedReport.objects.filter(feed=feed)
            .exclude(reason="")
            .values_list("reason", flat=True)
        )

        initial.append(
            {
                "feed_id": str(feed.uuid),
                "reason": "",
                "feed_title": feed.title,
                "feed_url": feed.feed_url,
                "known_reasons": list(known_reasons),
            }
        )

    return RemoveFeedsFormset(query_post, initial=initial)
