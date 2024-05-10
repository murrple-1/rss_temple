import uuid as uuid_
from typing import Any, cast

from django.db import IntegrityError, transaction
from django.db.models import OrderBy, Q
from django.http.response import HttpResponseBase
from drf_yasg.utils import swagger_auto_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api import fields as fieldutils
from api.exceptions import Conflict
from api.fields import FieldMap, generate_only_fields
from api.models import Feed, User, UserCategory
from api.serializers import (
    GetManySerializer,
    GetSingleSerializer,
    UserCategoryApplySerializer,
    UserCategoryCreateSerializer,
    UserCategorySerializer,
)

_OBJECT_NAME = "usercategory"


class UserCategoryView(APIView):
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        kwargs["uuid"] = uuid_.UUID(kwargs["uuid"])
        return super().dispatch(*args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Get Single User Category",
        operation_description="Get Single User Category",
        query_serializer=GetSingleSerializer,
    )
    def get(self, request: Request, *, uuid: uuid_.UUID):
        serializer = GetSingleSerializer(
            data=request.query_params,
            context={"object_name": _OBJECT_NAME, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        field_maps: list[FieldMap] = serializer.validated_data["fields"]

        user_category: UserCategory
        try:
            user_category = (
                UserCategory.objects.only(*generate_only_fields(field_maps))
                .prefetch_related("feeds")
                .get(uuid=uuid, user=cast(User, request.user))
            )
        except UserCategory.DoesNotExist:
            return Response("user category not found", status=404)

        ret_obj = fieldutils.generate_return_object(
            field_maps, user_category, request, None
        )

        return Response(ret_obj)

    @swagger_auto_schema(
        operation_summary="Update a User Category",
        operation_description="Update a User Category",
        request_body=UserCategorySerializer,
    )
    def put(self, request: Request, *, uuid: uuid_.UUID):
        user_category: UserCategory
        try:
            user_category = UserCategory.objects.get(
                uuid=uuid, user=cast(User, request.user)
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
            raise Conflict("user category already exists")

        return Response(status=204)

    @swagger_auto_schema(
        operation_summary="Delete a User Category",
        operation_description="Delete a User Category",
    )
    def delete(self, request: Request, *, uuid: uuid_.UUID):
        count, _ = UserCategory.objects.filter(
            uuid=uuid, user=cast(User, request.user)
        ).delete()

        if count < 1:
            raise NotFound("user category not found")

        return Response(status=204)


class UserCategoryCreateView(APIView):
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

        field_maps: list[FieldMap] = serializer.validated_data["fields"]

        user_category = UserCategory(
            user=cast(User, request.user), text=serializer.validated_data["text"]
        )

        try:
            user_category.save()
        except IntegrityError:
            raise Conflict("user category already exists")

        ret_obj = fieldutils.generate_return_object(
            field_maps, user_category, request, None
        )

        return Response(ret_obj)


class UserCategoriesQueryView(APIView):
    @swagger_auto_schema(
        operation_summary="Query for User Categories",
        operation_description="Query for User Categories",
        request_body=GetManySerializer,
    )
    def post(self, request: Request):
        serializer = GetManySerializer(
            data=request.data, context={"object_name": _OBJECT_NAME, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        count: int = serializer.validated_data["count"]
        skip: int = serializer.validated_data["skip"]
        sort: list[OrderBy] = serializer.validated_data["sort"]
        search: list[Q] = [
            Q(user=cast(User, request.user))
        ] + serializer.validated_data["search"]
        field_maps: list[FieldMap] = serializer.validated_data["fields"]
        return_objects: bool = serializer.validated_data["return_objects"]
        return_total_count: bool = serializer.validated_data["return_total_count"]

        user_categories = UserCategory.objects.filter(*search).only(
            *generate_only_fields(field_maps)
        )

        ret_obj: dict[str, Any] = {}

        if return_objects:
            objs: list[dict[str, Any]] = []
            for user_category in user_categories.prefetch_related("feeds").order_by(
                *sort
            )[skip : skip + count]:
                obj = fieldutils.generate_return_object(
                    field_maps, user_category, request, user_categories
                )
                objs.append(obj)

            ret_obj["objects"] = objs

        if return_total_count:
            ret_obj["totalCount"] = user_categories.count()

        return Response(ret_obj)


class UserCategoriesApplyView(APIView):
    @swagger_auto_schema(
        operation_summary="Add Feeds to a User Category",
        operation_description="Add Feeds to a User Category",
        request_body=UserCategoryApplySerializer,
    )
    def put(self, request: Request):
        serializer = UserCategoryApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mappings: dict[uuid_.UUID, frozenset[uuid_.UUID]] = serializer.validated_data[
            "mappings"
        ]

        all_feed_uuids: frozenset[uuid_.UUID] = frozenset(mappings.keys())
        all_user_category_uuids: set[uuid_.UUID] = set()

        for user_category_uuids in mappings.values():
            all_user_category_uuids.update(user_category_uuids)

        feeds: dict[uuid_.UUID, Feed] = {
            feed.uuid: feed for feed in Feed.objects.filter(uuid__in=all_feed_uuids)
        }

        if len(feeds) < len(all_feed_uuids):
            raise NotFound("feed not found")

        user_categories: dict[uuid_.UUID, UserCategory] = {
            user_category.uuid: user_category
            for user_category in UserCategory.objects.filter(
                uuid__in=all_user_category_uuids, user=cast(User, request.user)
            )
        }

        if len(user_categories) < len(all_user_category_uuids):
            raise NotFound("user category not found")

        with transaction.atomic():
            for feed_uuid, user_category_uuids in mappings.items():
                feeds[feed_uuid].user_categories.set(
                    [
                        user_categories[user_category_uuid]
                        for user_category_uuid in user_category_uuids
                    ]
                )

        return Response(status=204)
