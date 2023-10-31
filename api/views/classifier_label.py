import uuid

from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from drf_yasg.utils import swagger_auto_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
    FeedEntry,
)
from api.serializers import (
    ClassifierLabelListQuerySerializer,
    ClassifierLabelSerializer,
)


class ClassifierLabelListView(APIView):
    @swagger_auto_schema(
        query_serializer=ClassifierLabelListQuerySerializer,
        responses={200: ClassifierLabelSerializer(many=True)},
        operation_summary="Return a list of classifier labels",
        operation_description="Return a list of classifier labels",
    )
    def get(self, request: Request):
        serializer = ClassifierLabelListQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)

        classifier_labels = ClassifierLabel.objects.all()

        feed_entry_uuid: uuid.UUID | None = serializer.validated_data.get(
            "feed_entry_uuid"
        )
        if feed_entry_uuid is not None:
            if not FeedEntry.objects.filter(uuid=feed_entry_uuid).exists():
                raise NotFound("feed entry not found")

            classifier_labels = classifier_labels.annotate(
                vote_count=Coalesce(
                    Subquery(
                        ClassifierLabelFeedEntryVote.objects.filter(
                            feed_entry_id=feed_entry_uuid,
                            classifier_label_id=OuterRef("uuid"),
                        )
                        .values("feed_entry")
                        .annotate(c1=Count("uuid"))
                        .values("c1")
                    ),
                    0,
                )
                + Coalesce(
                    Subquery(
                        ClassifierLabelFeedEntryCalculated.objects.filter(
                            feed_entry_id=feed_entry_uuid,
                            classifier_label_id=OuterRef("uuid"),
                        )
                        .values("feed_entry")
                        .annotate(c2=Count("uuid"))
                        .values("c2")
                    ),
                    0,
                ),
            ).order_by("-vote_count", "text")
        else:
            classifier_labels = classifier_labels.order_by("text")

        return Response(ClassifierLabelSerializer(classifier_labels, many=True).data)
