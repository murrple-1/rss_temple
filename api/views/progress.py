from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import (
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
)


class FeedSubscriptionProgressView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, **kwargs):
        uuid_ = kwargs["uuid"]

        feed_subscription_progress_entry: FeedSubscriptionProgressEntry
        try:
            feed_subscription_progress_entry = (
                FeedSubscriptionProgressEntry.objects.get(uuid=uuid_, user=request.user)
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

        ret_obj: dict[str, int | str] = {
            "totalCount": total_count,
            "finishedCount": finished_count,
        }
        if (
            feed_subscription_progress_entry.status
            == FeedSubscriptionProgressEntry.NOT_STARTED
        ):
            ret_obj["state"] = "notstarted"
        elif (
            feed_subscription_progress_entry.status
            == FeedSubscriptionProgressEntry.STARTED
        ):
            ret_obj["state"] = "started"
        else:
            ret_obj["state"] = "finished"

        return Response(ret_obj)
