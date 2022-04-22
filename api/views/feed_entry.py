import re
import uuid

from django.core.cache import caches
from django_filters import rest_framework as filters
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from api.filters import FeedEntryFilter
from api.models import FeedEntry
from api.serializers import FeedEntrySerializer


class FeedEntryListView(generics.ListAPIView):
    serializer_class = FeedEntrySerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = FeedEntryFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FeedEntry.annotate_search_vectors(FeedEntry.objects.all())


class FeedEntryRetrieveView(generics.RetrieveAPIView):
    serializer_class = FeedEntrySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"

    def get_queryset(self):
        return FeedEntry.objects.all()


class FeedEntryStableListView(generics.ListAPIView):
    serializer_class = FeedEntrySerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = FeedEntryFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        cache = caches["stable_query"]

        token = self.request.query_params.get("token")
        if token is None:
            raise ValidationError({"token": "missing"})

        if re.search(r"^feedentry-\d+$", token) is None:
            raise ValidationError({"token": "malformed"})

        cache.touch(token)
        uuids = cache.get(token, [])

        return FeedEntry.objects.filter(uuid__in=uuids)

    def post(self, request: Request):
        cache = caches["stable_query"]

        qs = FeedEntryFilter(
            self.request.query_params,
            queryset=FeedEntry.annotate_search_vectors(FeedEntry.objects.all()),
        ).qs

        token = f"feedentry-{uuid.uuid4().int}"

        cache.set(
            token,
            list(qs.values_list("uuid", flat=True)),
        )

        return Response(token)


class FeedEntryReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request):
        qs = FeedEntryFilter(
            self.request.query_params,
            queryset=FeedEntry.annotate_search_vectors(FeedEntry.objects.all()),
        ).qs

        feed_entry_uuids = list(qs.values_list("uuid", flat=True))

        request.user.read_feed_entries.add(*feed_entry_uuids)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request):
        qs = FeedEntryFilter(
            self.request.query_params,
            queryset=FeedEntry.annotate_search_vectors(FeedEntry.objects.all()),
        ).qs

        feed_entry_uuids = list(qs.values_list("uuid", flat=True))

        request.user.read_feed_entries.remove(*feed_entry_uuids)

        return Response(status=status.HTTP_204_NO_CONTENT)


class FeedEntryFavoriteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request):
        qs = FeedEntryFilter(
            self.request.query_params,
            queryset=FeedEntry.annotate_search_vectors(FeedEntry.objects.all()),
        ).qs

        feed_entry_uuids = list(qs.values_list("uuid", flat=True))

        request.user.favorite_feed_entries.add(*feed_entry_uuids)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request):
        qs = FeedEntryFilter(
            self.request.query_params,
            queryset=FeedEntry.annotate_search_vectors(FeedEntry.objects.all()),
        ).qs

        feed_entry_uuids = list(qs.values_list("uuid", flat=True))

        request.user.favorite_feed_entries.remove(*feed_entry_uuids)

        return Response(status=status.HTTP_204_NO_CONTENT)
