import random
import uuid as uuid_
from typing import Any, Iterable, cast

from django.core.cache import BaseCache, caches
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.http.response import HttpResponseBase
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.cache_utils.classifier_label_vote_counts import (
    get_classifier_label_vote_counts_from_cache,
)
from api.models import ClassifierLabel, ClassifierLabelFeedEntryVote, FeedEntry, User
from api.serializers import (
    ClassifierLabelListByEntryBodySerializer,
    ClassifierLabelListByEntrySerializer,
    ClassifierLabelListQuerySerializer,
    ClassifierLabelSerializer,
    ClassifierLabelVotesListQuerySerializer,
    ClassifierLabelVotesListSerializer,
    ClassifierLabelVotesSerializer,
)


class ClassifierLabelListView(APIView):
    @extend_schema(
        parameters=[ClassifierLabelListQuerySerializer],
        responses=ClassifierLabelSerializer(many=True),
        summary="Return a list of classifier labels",
        description="Return a list of classifier labels",
    )
    def get(self, request: Request):
        cache: BaseCache = caches["default"]

        serializer = ClassifierLabelListQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)

        feed_entry_uuid: uuid_.UUID | None = serializer.validated_data.get(
            "feed_entry_uuid"
        )

        classifier_labels: Iterable[ClassifierLabel]
        cache_hit: bool | None = None
        if feed_entry_uuid is not None:
            if not FeedEntry.objects.filter(uuid=feed_entry_uuid).exists():
                raise NotFound("feed entry not found")

            (
                classifier_label_vote_counts,
                cache_hit,
            ) = get_classifier_label_vote_counts_from_cache((feed_entry_uuid,), cache)

            vote_counts = classifier_label_vote_counts[feed_entry_uuid]

            classifier_labels = ClassifierLabel.objects.annotate(
                vote_count=Case(
                    *(
                        When(condition=Q(uuid=uuid), then=Value(count))
                        for uuid, count in vote_counts.items()
                    ),
                    default=Value(-1),
                    output_field=IntegerField()
                )
            ).order_by("-vote_count", "?")
        else:
            classifier_labels = ClassifierLabel.objects.order_by("?")

        response = Response(
            ClassifierLabelSerializer(classifier_labels, many=True).data
        )
        if cache_hit is not None:
            response["X-Cache-Hit"] = ",".join(("YES" if cache_hit else "NO",))
        return response


class ClassifierLabelListByEntryView(APIView):
    @extend_schema(
        responses=ClassifierLabelListByEntrySerializer,
        summary="Return lists of classifier labels, by feed entry UUIDs",
        description="Return lists of classifier labels, by feed entry UUIDs",
        request=ClassifierLabelListByEntryBodySerializer,
    )
    def post(self, request: Request):
        cache: BaseCache = caches["default"]

        serializer = ClassifierLabelListByEntryBodySerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        feed_entry_uuids: frozenset[uuid_.UUID] = frozenset(
            serializer.validated_data["feed_entry_uuids"]
        )

        if FeedEntry.objects.filter(uuid__in=feed_entry_uuids).count() != len(
            feed_entry_uuids
        ):
            raise NotFound("feed entry not found")

        (
            classifier_label_vote_counts,
            cache_hit,
        ) = get_classifier_label_vote_counts_from_cache(feed_entry_uuids, cache)

        classifier_labels = list(ClassifierLabel.objects.all())

        classifier_labels_by_feed_entry_uuid: dict[str, list[ClassifierLabel]] = {}

        for feed_entry_uuid, vote_counts in classifier_label_vote_counts.items():
            classifier_labels_with_order_keys: list[
                tuple[ClassifierLabel, tuple[int, float]]
            ] = [
                (
                    classifier_label,
                    (vote_counts.get(classifier_label.uuid, -1), random.random()),
                )
                for classifier_label in classifier_labels
            ]
            classifier_labels_with_order_keys.sort(key=lambda t: t[1], reverse=True)

            classifier_labels_by_feed_entry_uuid[str(feed_entry_uuid)] = [
                t[0] for t in classifier_labels_with_order_keys
            ]

        response = Response(
            ClassifierLabelListByEntrySerializer(
                {"classifier_labels": classifier_labels_by_feed_entry_uuid}
            ).data
        )
        response["X-Cache-Hit"] = ",".join(("YES" if cache_hit else "NO",))
        return response


class ClassifierLabelFeedEntryVotesView(APIView):
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(*args, **kwargs)

    @extend_schema(
        responses=ClassifierLabelSerializer(many=True),
        summary="Return a list of classifier labels voted for by current user on feed entry",
        description="Return a list of classifier labels voted for by current user on feed entry",
    )
    def get(self, request: Request, *, uuid: uuid_.UUID):
        user = cast(User, request.user)

        if not FeedEntry.objects.filter(uuid=uuid).exists():
            raise NotFound("feed entry not found")

        classifier_labels = ClassifierLabel.objects.filter(
            uuid__in=ClassifierLabelFeedEntryVote.objects.filter(
                feed_entry_id=uuid, user=user
            ).values("classifier_label_id")
        )

        return Response(ClassifierLabelSerializer(classifier_labels, many=True).data)

    @extend_schema(
        responses={204: OpenApiResponse(description="No response body")},
        request=ClassifierLabelVotesSerializer,
        summary="Submit Classifier Label votes for a feed entry",
        description="Submit Classifier Label votes for a feed entry",
    )
    def post(self, request: Request, *, uuid: uuid_.UUID):
        user = cast(User, request.user)

        serializer = ClassifierLabelVotesSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        classifier_label_uuids = frozenset(
            serializer.validated_data["classifier_label_uuids"]
        )

        if not FeedEntry.objects.filter(uuid=uuid).exists():
            raise NotFound("feed entry not found")

        if ClassifierLabel.objects.filter(
            uuid__in=classifier_label_uuids
        ).count() < len(classifier_label_uuids):
            raise NotFound("classifier label not found")

        with transaction.atomic():
            ClassifierLabelFeedEntryVote.objects.filter(
                user=user, feed_entry_id=uuid
            ).delete()
            ClassifierLabelFeedEntryVote.objects.bulk_create(
                ClassifierLabelFeedEntryVote(
                    user=user,
                    feed_entry_id=uuid,
                    classifier_label_id=classifier_label_uuid,
                )
                for classifier_label_uuid in classifier_label_uuids
            )

        return Response(status=204)


class ClassifierLabelVotesListView(APIView):
    @extend_schema(
        summary="Query for Classifier Label votes",
        description="Query for Classifier Label votes",
        parameters=[ClassifierLabelVotesListQuerySerializer],
        responses=ClassifierLabelVotesListSerializer,
    )
    def get(self, request: Request):
        user = cast(User, request.user)

        serializer = ClassifierLabelVotesListQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)

        count: int = serializer.validated_data["count"]
        skip: int = serializer.validated_data["skip"]

        feed_entries = FeedEntry.objects.filter(
            uuid__in=ClassifierLabelFeedEntryVote.objects.filter(user=user).values(
                "feed_entry_id"
            )
        )

        ret_obj: dict[str, Any] = {
            "totalCount": feed_entries.count(),
        }

        feed_entry_vote_mappings: dict[uuid_.UUID, list[uuid_.UUID]] = {
            uuid: []
            for uuid in feed_entries.order_by("uuid")
            .values_list("uuid", flat=True)[skip : skip + count]
            .iterator()
        }

        for classifier_label_vote_dict in (
            ClassifierLabelFeedEntryVote.objects.filter(
                user=user, feed_entry_id__in=feed_entry_vote_mappings.keys()
            )
            .values("feed_entry_id", "classifier_label_id")
            .iterator()
        ):
            feed_entry_vote_mappings[
                classifier_label_vote_dict["feed_entry_id"]
            ].append(classifier_label_vote_dict["classifier_label_id"])

        ret_obj["objects"] = [
            {
                "feedEntryUuid": feed_entry_uuid,
                "classifierLabelUuids": classifier_label_uuids,
            }
            for feed_entry_uuid, classifier_label_uuids in feed_entry_vote_mappings.items()
        ]

        return Response(ClassifierLabelVotesListSerializer(ret_obj).data)
