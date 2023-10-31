import uuid
from collections import Counter
from typing import Any

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.core.signals import setting_changed
from django.db.models import Case, When
from django.dispatch import receiver
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

_CLASSIFIER_LABEL_VOTES_CACHE_TIMEOUT_SECONDS: float


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _CLASSIFIER_LABEL_VOTES_CACHE_TIMEOUT_SECONDS

    _CLASSIFIER_LABEL_VOTES_CACHE_TIMEOUT_SECONDS = (
        settings.CLASSIFIER_LABEL_VOTES_CACHE_TIMEOUT_SECONDS
    )


_load_global_settings()


class ClassifierLabelListView(APIView):
    @swagger_auto_schema(
        query_serializer=ClassifierLabelListQuerySerializer,
        responses={200: ClassifierLabelSerializer(many=True)},
        operation_summary="Return a list of classifier labels",
        operation_description="Return a list of classifier labels",
    )
    def get(self, request: Request):
        cache: BaseCache = caches["default"]

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

            cache_key = f"classifier_label_votes__{feed_entry_uuid}"
            counter: Counter | None = cache.get(cache_key)
            if counter is None:
                counter = Counter(
                    ClassifierLabelFeedEntryCalculated.objects.filter(
                        feed_entry_id=feed_entry_uuid
                    ).values_list("classifier_label__text", flat=True)
                ) + Counter(
                    ClassifierLabelFeedEntryVote.objects.filter(
                        feed_entry_id=feed_entry_uuid
                    )
                    .values_list("classifier_label__text", flat=True)
                    .iterator()
                )
                cache.set(
                    cache_key, counter, _CLASSIFIER_LABEL_VOTES_CACHE_TIMEOUT_SECONDS
                )

            whens = [
                When(text=value, then=count) for value, count in counter.most_common()
            ]
            classifier_labels = classifier_labels.annotate(
                vote_count=Case(
                    *whens,
                    default=0,
                )
            ).order_by("-vote_count", "text")
        else:
            classifier_labels = classifier_labels.order_by("text")

        return Response(ClassifierLabelSerializer(classifier_labels, many=True).data)
