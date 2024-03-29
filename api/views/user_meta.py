from typing import cast

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import User


class ReadCountView(APIView):
    @swagger_auto_schema(
        operation_summary="Get the number of read entries for a user",
        operation_description="Get the number of read entries for a user",
        responses={200: openapi.Schema(type="number")},
    )
    def get(self, request: Request):
        return Response(cast(User, request.user).read_feed_entries_counter)
