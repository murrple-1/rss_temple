import uuid
from typing import Any, cast

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)

from api import query_utils
from api.decorators import requires_authenticated_user
from api.models import (
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
    User,
)


@requires_authenticated_user()
def feed_subscription_progress(request: HttpRequest, uuid_: str) -> HttpResponseBase:
    uuid__ = uuid.UUID(uuid_)

    permitted_methods = {"GET"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "GET":
        return _feed_subscription_progress_get(request, uuid__)
    else:  # pragma: no cover
        raise ValueError


def _feed_subscription_progress_get(request: HttpRequest, uuid_: uuid.UUID):
    feed_subscription_progress_entry: FeedSubscriptionProgressEntry
    try:
        feed_subscription_progress_entry = FeedSubscriptionProgressEntry.objects.get(
            uuid=uuid_, user=cast(User, request.user)
        )
    except FeedSubscriptionProgressEntry.DoesNotExist:
        return HttpResponseNotFound("progress not found")

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

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)
