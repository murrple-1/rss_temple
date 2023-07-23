import uuid
from typing import Any, cast

from django.http.request import HttpRequest
from django.http.response import HttpResponseBase
from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import (
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
    User,
)


class FeedSubscriptionProgressView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        kwargs["uuid"] = uuid.UUID(kwargs["uuid"])
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: Request, **kwargs: Any):
        feed_subscription_progress_entry: FeedSubscriptionProgressEntry
        try:
            feed_subscription_progress_entry = (
                FeedSubscriptionProgressEntry.objects.get(
                    uuid=kwargs["uuid"], user=cast(User, request.user)
                )
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
            feed_subscription_progress_entry.status
            == FeedSubscriptionProgressEntry.STARTED
        ):
            ret_obj["state"] = "started"
        else:
            ret_obj["state"] = "finished"

        return Response(ret_obj)
