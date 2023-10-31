import uuid
from collections import Counter

from django.db.models import Case, When
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
            feed_entry: FeedEntry
            try:
                feed_entry = FeedEntry.objects.get(uuid=feed_entry_uuid)
            except FeedEntry.DoesNotExist:
                raise NotFound("feed entry not found")

            labels = list(
                ClassifierLabelFeedEntryCalculated.objects.filter(
                    feed_entry=feed_entry
                ).values_list("classifier_label__text", flat=True)
            ) + list(
                ClassifierLabelFeedEntryVote.objects.filter(
                    feed_entry=feed_entry
                ).values_list("classifier_label__text", flat=True)
            )
            counter = Counter(labels)
            whens = [
                When(text=value, then=count) for value, count in counter.most_common()
            ]
            classifier_labels = classifier_labels.annotate(
                vote_count=Case(
                    *whens,
                    default=0,
                )
            ).order_by("-vote_count")
        else:
            classifier_labels = classifier_labels.order_by("text")

        return Response(ClassifierLabelSerializer(classifier_labels, many=True).data)
