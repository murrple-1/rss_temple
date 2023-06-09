import uuid

from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound

from api import query_utils
from api.models import (
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
)


def feed_subscription_progress(request, uuid_):
    uuid_ = uuid.UUID(uuid_)

    permitted_methods = {"GET"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "GET":
        return _feed_subscription_progress_get(request, uuid_)


def _feed_subscription_progress_get(request, uuid_):
    feed_subscription_progress_entry = None
    try:
        feed_subscription_progress_entry = FeedSubscriptionProgressEntry.objects.get(
            uuid=uuid_, user=request.user
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

    ret_obj = {
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
