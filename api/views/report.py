from typing import cast

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import FeedEntry, FeedEntryReport, FeedReport, User, Feed
from api.serializers import FeedEntryReportBodySerializer, FeedReportBodySerializer


class FeedReportView(APIView):
    @extend_schema(
        summary="Query for Feeds",
        description="Query for Feeds",
        request=FeedReportBodySerializer,
        responses={204: OpenApiResponse(description="No response body")},
    )
    def post(self, request: Request):
        user = cast(User, request.user)

        serializer = FeedReportBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed: Feed
        try:
            feed = Feed.objects.get(uuid=serializer.validated_data["feed_uuid"])
        except Feed.DoesNotExist:
            raise NotFound("feed not found")

        FeedReport.objects.create(
            feed=feed, user=user, reason=serializer.validated_data["reason"]
        )

        return Response(status=204)


class FeedEntryReportView(APIView):
    @extend_schema(
        summary="Query for Feeds",
        description="Query for Feeds",
        request=FeedEntryReportBodySerializer,
        responses={204: OpenApiResponse(description="No response body")},
    )
    def post(self, request: Request):
        user = cast(User, request.user)

        serializer = FeedEntryReportBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feed_entry: FeedEntry
        try:
            feed_entry = FeedEntry.objects.get(
                uuid=serializer.validated_data["feed_entry_uuid"]
            )
        except FeedEntry.DoesNotExist:
            raise NotFound("feed entry not found")

        FeedEntryReport.objects.create(
            feed_entry=feed_entry, user=user, reason=serializer.validated_data["reason"]
        )

        return Response(status=204)
