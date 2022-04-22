import logging
from typing import cast

from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.request import Request

from api.models import VerificationToken, User
from api.serializers import UserSerializer

_logger = logging.getLogger("rss_temple")


class UserRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserVerifyView(generics.GenericAPIView):
    def post(self, request: Request):
        token = request.query_params.get("token")

        if token is None:
            raise ValidationError({"token": "missing"})

        verification_token = VerificationToken.find_by_token(token)

        if verification_token is None:
            raise NotFound("token not found")

        verification_token.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class UserAttributesView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def put(self, request: Request):
        if type(request.data) is not dict:
            raise ValidationError("body must be object")  # pragma: no cover

        user = cast(User, request.user)

        user.attributes.update(request.data)

        del_keys = set()
        for key, value in user.attributes.items():
            if value is None:
                del_keys.add(key)

        for key in del_keys:
            del user.attributes[key]

        user.save(update_fields=["attributes"])

        return Response(status=status.HTTP_204_NO_CONTENT)
