import uuid

from django.db import IntegrityError, transaction
from django_filters import rest_framework as filters
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from api.exceptions import Conflict
from api.filters import UserCategoryFilter
from api.models import Feed, UserCategory
from api.serializers import UserCategorySerializer


class UserCategoryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserCategorySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"

    def get_queryset(self):
        return UserCategory.objects.filter(user=self.request.user)

    def update(self, request: Request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except IntegrityError:
            raise Conflict()

    def partial_update(self, request: Request, *args, **kwargs):
        try:
            return super().partial_update(request, *args, **kwargs)
        except IntegrityError:
            raise Conflict()


class UserCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = UserCategorySerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = UserCategoryFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserCategory.objects.filter(user=self.request.user)

    def create(self, request: Request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            raise Conflict()


class UserCategoryApplyView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def put(self, request: Request):
        if type(request.data) is not dict:
            raise ValidationError("body must be object")  # pragma: no cover

        all_feed_uuids: set[uuid.UUID] = set()
        all_user_category_uuids: set[uuid.UUID] = set()

        mappings: dict[uuid.UUID, frozenset[uuid.UUID]] = {}

        for feed_uuid, user_category_uuids in request.data.items():
            feed_uuid_: uuid.UUID
            try:
                feed_uuid_ = uuid.UUID(feed_uuid)
            except ValueError:
                raise ValidationError("body key malformed")

            all_feed_uuids.add(feed_uuid_)

            if type(user_category_uuids) is not list:
                raise ValidationError("body element must be array")

            try:
                user_category_uuids = frozenset(
                    uuid.UUID(s) for s in user_category_uuids
                )
            except (ValueError, TypeError):
                raise ValidationError("value malformed")

            all_user_category_uuids.update(user_category_uuids)

            mappings[feed_uuid_] = user_category_uuids

        feeds: dict[uuid.UUID, Feed] = {
            feed.uuid: feed for feed in Feed.objects.filter(uuid__in=all_feed_uuids)
        }

        if len(feeds) < len(all_feed_uuids):
            raise NotFound("feed not found")

        user_categories: dict[uuid.UUID, UserCategory] = {
            user_category.uuid: user_category
            for user_category in UserCategory.objects.filter(
                uuid__in=all_user_category_uuids, user=request.user
            )
        }

        if len(user_categories) < len(all_user_category_uuids):
            raise NotFound("user category not found")

        with transaction.atomic():
            for feed_uuid, user_category_uuids in mappings.items():
                feed = feeds[feed_uuid]
                feed.user_categories.clear()
                feed.user_categories.add(*user_category_uuids)

        return Response(status=status.HTTP_204_NO_CONTENT)
