import uuid as uuid_
from typing import Any, cast

from django.http.response import HttpResponseBase
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
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
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(*args, **kwargs)

    @extend_schema(
        summary="Check on the progress of your subscription queue entry",
        description="Check on the progress of your subscription queue entry",
        responses=inline_serializer(
            "FeedSubscriptionProgressSerializer",
            {
                "totalCount": serializers.IntegerField(),
                "finishedCount": serializers.IntegerField(),
            },
        ),
    )
    def get(self, request: Request, *, uuid: uuid_.UUID):
        feed_subscription_progress_entry: FeedSubscriptionProgressEntry
        try:
            feed_subscription_progress_entry = (
                FeedSubscriptionProgressEntry.objects.get(
                    uuid=uuid, user=cast(User, request.user)
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
