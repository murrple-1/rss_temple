import uuid
from typing import Any, cast

from django.db import IntegrityError, transaction
from django.db.models import OrderBy, Q
from django.http.request import HttpRequest
from django.http.response import HttpResponseBase
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api import query_utils
from api.fields import FieldMap
from api.models import Feed, User, UserCategory
from api.serializers import (
    GetMultipleSerializer,
    GetSingleSerializer,
    UserCategoryCreateSerializer,
    UserCategorySerializer,
)

_OBJECT_NAME = "usercategory"


class UserCategoryView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        kwargs["uuid"] = uuid.UUID(kwargs["uuid"])
        return super().dispatch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Get Single User Category",
        operation_description="Get Single User Category",
        query_serializer=GetSingleSerializer,
    )
    def get(self, request: Request, **kwargs: Any):
        serializer = GetSingleSerializer(
            data=request.query_params,
            context={"object_name": _OBJECT_NAME, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        field_maps: list[FieldMap] = serializer.data["my_fields"]

        user_category: UserCategory
        try:
            user_category = UserCategory.objects.get(
                uuid=kwargs["uuid"], user=cast(User, request.user)
            )
        except UserCategory.DoesNotExist:
            return Response("user category not found", status=404)

        ret_obj = query_utils.generate_return_object(field_maps, user_category, request)

        return Response(ret_obj)

    @swagger_auto_schema(
        operation_summary="Update a User Category",
        operation_description="Update a User Category",
        request_body=UserCategorySerializer,
    )
    def put(self, request: Request, **kwargs: Any):
        user_category: UserCategory
        try:
            user_category = UserCategory.objects.get(
                uuid=kwargs["uuid"], user=cast(User, request.user)
            )
        except UserCategory.DoesNotExist:
            return Response("user category not found", status=404)

        serializer = UserCategorySerializer(
            instance=user_category, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError:
            return Response("user category already exists", status=409)

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Delete a User Category",
        operation_description="Delete a User Category",
    )
    def delete(self, request: Request, **kwargs: Any):
        count, _ = UserCategory.objects.filter(
            uuid=kwargs["uuid"], user=cast(User, request.user)
        ).delete()

        if count < 1:
            raise NotFound("user category not found")

        return Response(status=204)


class UserCategoryCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_summary="Create a User Category",
        operation_description="Create a User Category",
        request_body=UserCategoryCreateSerializer,
    )
    def post(self, request: Request):
        serializer = UserCategoryCreateSerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        field_maps: list[FieldMap] = serializer.data["my_fields"]

        user_category = UserCategory(
            user=cast(User, request.user), text=serializer.data["text"]
        )

        try:
            user_category.save()
        except IntegrityError:
            return Response("user category already exists", status=409)

        ret_obj = query_utils.generate_return_object(field_maps, user_category, request)

        return Response(ret_obj)


class UserCategoriesQueryView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_summary="Query for User Categories",
        operation_description="Query for User Categories",
        request_body=GetMultipleSerializer,
    )
    def post(self, request: Request):
        serializer = GetMultipleSerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        count: int = serializer.data["count"]
        skip: int = serializer.data["skip"]
        sort: list[OrderBy] = serializer.data["sort"]
        search: list[Q] = serializer.get_filter_args(request)
        field_maps: list[FieldMap] = serializer.data["my_fields"]
        return_objects: bool = serializer.data["return_objects"]
        return_total_count: bool = serializer.data["return_total_count"]

        user_categories = UserCategory.objects.filter(*search)

        ret_obj: dict[str, Any] = {}

        if return_objects:
            objs: list[dict[str, Any]] = []
            for user_category in user_categories.order_by(*sort)[skip : skip + count]:
                obj = query_utils.generate_return_object(
                    field_maps, user_category, request
                )
                objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = user_categories.count()

        return Response(ret_obj)


class UserCategoriesApplyView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_summary="Add Feeds to a User Category",
        operation_description="Add Feeds to a User Category",
        request_body=openapi.Schema(type="object"),
    )
    def put(self, request: Request):
        all_feed_uuids: set[uuid.UUID] = set()
        all_user_category_uuids: set[uuid.UUID] = set()

        mappings: dict[uuid.UUID, frozenset[uuid.UUID]] = {}

        for feed_uuid, user_category_uuids in request.data.items():
            feed_uuid_: uuid.UUID
            try:
                feed_uuid_ = uuid.UUID(feed_uuid)
            except ValueError:
                raise ValidationError({".[]": "key malformed"})

            all_feed_uuids.add(feed_uuid_)

            if type(user_category_uuids) is not list:
                raise ValidationError({".[]": "must be array"})

            try:
                user_category_uuids = frozenset(
                    uuid.UUID(s) for s in user_category_uuids
                )
            except (ValueError, TypeError):
                raise ValidationError({".[]": "malformed"})

            all_user_category_uuids.update(user_category_uuids)

            mappings[feed_uuid_] = user_category_uuids

        feeds = {
            feed.uuid: feed for feed in Feed.objects.filter(uuid__in=all_feed_uuids)
        }

        if len(feeds) < len(all_feed_uuids):
            raise NotFound("feed not found")

        user_categories = {
            user_category.uuid: user_category
            for user_category in UserCategory.objects.filter(
                uuid__in=all_user_category_uuids, user=cast(User, request.user)
            )
        }

        if len(user_categories) < len(all_user_category_uuids):
            raise NotFound("user category not found")

        with transaction.atomic():
            for feed_uuid_, user_category_uuids in mappings.items():
                feed = feeds[feed_uuid_]
                feed.user_categories.clear()

                feed.user_categories.add(
                    *(
                        user_categories[user_category_uuid]
                        for user_category_uuid in user_category_uuids
                    )
                )

        return Response(status=204)
