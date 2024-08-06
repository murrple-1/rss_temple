from typing import cast

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import User


class ReadCountView(APIView):
    @extend_schema(
        summary="Get the number of read entries for a user",
        description="Get the number of read entries for a user",
        responses=OpenApiTypes.NUMBER,
    )
    def get(self, request: Request):
        return Response(cast(User, request.user).read_feed_entries_counter)
