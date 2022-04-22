from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import NotifyEmailQueueEntry, NotifyEmailQueueEntryRecipient, User
from api.render import passwordreset as passwordresetrender


class PasswordResetRequestView(generics.GenericAPIView):
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request: Request):
        email: str
        try:
            email = request.data["email"]
        except KeyError:
            raise ValidationError({"email": "missing"})

        user: User
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)

        token_str: str = default_token_generator.make_token(user)

        subject = passwordresetrender.subject()
        plain_text = passwordresetrender.plain_text(token_str)
        html_text = passwordresetrender.html_text(token_str)

        with transaction.atomic():
            email_queue_entry = NotifyEmailQueueEntry.objects.create(
                subject=subject, plain_text=plain_text, html_text=html_text
            )
            NotifyEmailQueueEntryRecipient.objects.create(
                type=NotifyEmailQueueEntryRecipient.TYPE_TO,
                email=email,
                entry=email_queue_entry,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetView(generics.GenericAPIView):
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request: Request):
        email: str
        try:
            email = request.data["email"]
        except KeyError:
            raise ValidationError({"email": "missing"})

        token: str
        try:
            token = request.data["token"]
        except KeyError:
            raise ValidationError({"token": "missing"})

        password: str
        try:
            password = request.data["password"]
        except KeyError:
            raise ValidationError({"password": "missing"})

        user: User
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise NotFound("token invalid")

        if not default_token_generator.check_token(user, token):
            raise NotFound("token invalid")

        user.set_password(password)

        return Response(status=status.HTTP_204_NO_CONTENT)
