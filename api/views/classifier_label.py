import uuid as uuid_
from typing import Any, cast

from django.db import transaction
from django.db.models import Count, OuterRef, QuerySet, Subquery
from django.db.models.functions import Coalesce
from django.http.response import HttpResponseBase
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
    User,
)
from api.serializers import (
    ClassifierLabelListQuerySerializer,
    ClassifierLabelSerializer,
    ClassifierLabelVotesListQuerySerializer,
    ClassifierLabelVotesListSerializer,
    ClassifierLabelVotesSerializer,
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

        feed_entry_uuid: uuid_.UUID | None = serializer.validated_data.get(
            "feed_entry_uuid"
        )

        classifier_labels: QuerySet[ClassifierLabel]
        if feed_entry_uuid is not None:
            if not FeedEntry.objects.filter(uuid=feed_entry_uuid).exists():
                raise NotFound("feed entry not found")

            classifier_labels = ClassifierLabel.objects.annotate(
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
            ).order_by("-vote_count", "?")
        else:
            classifier_labels = ClassifierLabel.objects.order_by("?")

        return Response(ClassifierLabelSerializer(classifier_labels, many=True).data)


class ClassifierLabelFeedEntryVotesView(APIView):
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(*args, **kwargs)

    @swagger_auto_schema(
        responses={200: ClassifierLabelSerializer(many=True)},
        operation_summary="Return a list of classifier labels voted for by current user on feed entry",
        operation_description="Return a list of classifier labels voted for by current user on feed entry",
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

    @swagger_auto_schema(
        responses={204: ""},
        request_body=ClassifierLabelVotesSerializer,
        operation_summary="Submit Classifier Label votes for a feed entry",
        operation_description="Submit Classifier Label votes for a feed entry",
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
    @swagger_auto_schema(
        operation_summary="Query for Classifier Label votes",
        operation_description="Query for Classifier Label votes",
        query_serializer=ClassifierLabelVotesListQuerySerializer,
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
