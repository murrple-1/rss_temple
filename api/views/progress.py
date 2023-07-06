import uuid
from typing import Any, cast

from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import (
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
    User,
)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def feed_subscription_progress(request: Request, uuid_: str) -> Response:
    uuid__ = uuid.UUID(uuid_)

    if request.method == "GET":
        return _feed_subscription_progress_get(request, uuid__)
    else:  # pragma: no cover
        raise ValueError


def _feed_subscription_progress_get(request: Request, uuid_: uuid.UUID):
    feed_subscription_progress_entry: FeedSubscriptionProgressEntry
    try:
        feed_subscription_progress_entry = FeedSubscriptionProgressEntry.objects.get(
            uuid=uuid_, user=cast(User, request.user)
        )
    except FeedSubscriptionProgressEntry.DoesNotExist:
        raise NotFound("progress not found")

    progress_statuses = list(
        FeedSubscriptionProgressEntryDescriptor.objects.filter(
            feed_subscription_progress_entry=feed_subscription_progress_entry
        ).values_list("is_finished", flat=True)
    )

    total_count = len(progress_statuses)

    finished_count = sum(1 for is_finished in progress_statuses if is_finished)

    ret_obj: dict[str, Any] = {
        "totalCount": total_count,
        "finishedCount": finished_count,
    }
    if (
        feed_subscription_progress_entry.status
        == FeedSubscriptionProgressEntry.NOT_STARTED
    ):
        ret_obj["state"] = "notstarted"
    elif (
        feed_subscription_progress_entry.status == FeedSubscriptionProgressEntry.STARTED
    ):
        ret_obj["state"] = "started"
    else:
        ret_obj["state"] = "finished"

    return Response(ret_obj)
