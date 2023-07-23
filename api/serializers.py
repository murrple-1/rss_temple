from typing import cast

from allauth.account.adapter import get_adapter
from allauth.account.forms import PasswordVerificationMixin, SetPasswordField, UserForm
from dj_rest_auth.app_settings import api_settings
from dj_rest_auth.serializers import LoginSerializer as _LoginSerializer
from dj_rest_auth.serializers import UserDetailsSerializer as _UserDetailsSerializer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http.request import HttpRequest
from django.urls import exceptions as url_exceptions
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

try:
    from allauth.account import app_settings as allauth_account_settings
    from allauth.account.adapter import get_adapter
    from allauth.account.utils import setup_user_email
    from allauth.utils import email_address_exists, get_username_max_length
except ImportError:
    raise ImportError("allauth needs to be added to INSTALLED_APPS.")

from api.models import User


class LoginSerializer(_LoginSerializer):
    def get_auth_user(self, username, email, password):
        """
        Retrieve the auth user from given POST payload by using
        either `allauth` auth scheme or bare Django auth scheme.

        Returns the authenticated user instance if credentials are correct,
        else `None` will be returned
        """
        if "allauth" in settings.INSTALLED_APPS:
            # When `is_active` of a user is set to False, allauth tries to return template html
            # which does not exist. This is the solution for it. See issue #264.
            try:
                return self.get_auth_user_using_allauth(username, email, password)
            except url_exceptions.NoReverseMatch:
                raise AuthenticationFailed(
                    "Unable to log in with provided credentials."
                )
        return self.get_auth_user_using_orm(username, email, password)

    def validate(self, attrs):
        username = attrs.get("username")
        email = attrs.get("email")
        password = attrs.get("password")
        user = self.get_auth_user(username, email, password)

        if not user:
            raise AuthenticationFailed("Unable to log in with provided credentials.")

        # Did we get back an active user?
        self.validate_auth_user_status(user)

        # If required, is the email verified?
        if "dj_rest_auth.registration" in settings.INSTALLED_APPS:
            self.validate_email_verification_status(user, email=email)

        attrs["user"] = user
        return attrs


class UserDetailsSerializer(serializers.ModelSerializer):
    subscribedFeedUuids = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True, source="subscribed_feeds"
    )

    class Meta(_UserDetailsSerializer.Meta):
        model = User
        fields = ("uuid", "email", "subscribedFeedUuids", "attributes")
        read_only_fields = ("uuid", "email", "attributes")


class _SetPasswordForm(PasswordVerificationMixin, UserForm):
    password = SetPasswordField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setattr(self.fields["password"], "user", self.user)

    def save(self):
        get_adapter().set_password(self.user, self.cleaned_data["password"])


class PasswordChangeSerializer(serializers.Serializer):
    oldPassword = serializers.CharField(max_length=128)
    newPassword = serializers.CharField(max_length=128)

    set_password_form: _SetPasswordForm | None = None

    request: HttpRequest

    def __init__(self, *args, **kwargs):
        self.logout_on_password_change = api_settings.LOGOUT_ON_PASSWORD_CHANGE
        super().__init__(*args, **kwargs)

        self.request = self.context["request"]

    def validate_oldPassword(self, value):
        if self.request.user and not self.request.user.check_password(value):
            err_msg = (
                "Your old password was entered incorrectly. Please enter it again."
            )

            raise serializers.ValidationError(err_msg)
        return value

    def validate(self, attrs):
        self.set_password_form = _SetPasswordForm(
            user=self.request.user,
            data={"password": attrs["newPassword"]},
        )

        if not self.set_password_form.is_valid():
            raise serializers.ValidationError(self.set_password_form.errors)
        return attrs

    def save(self):
        assert self.set_password_form

        self.set_password_form.save()
        if not self.logout_on_password_change:
            from django.contrib.auth import update_session_auth_hash

            update_session_auth_hash(self.request, self.request.user)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming a password reset attempt.
    """

    newPassword = serializers.CharField(max_length=128)
    userUuid = serializers.UUIDField()
    token = serializers.CharField()

    set_password_form: _SetPasswordForm | None = None

    def validate(self, attrs):
        if "allauth" in settings.INSTALLED_APPS:
            from allauth.account.forms import default_token_generator
        else:
            from django.contrib.auth.tokens import default_token_generator

        UserModel = get_user_model()

        try:
            user = UserModel.objects.get(pk=attrs["userUuid"])
        except UserModel.DoesNotExist:
            raise serializers.ValidationError({"userUuid": "Invalid value"})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Invalid value"})

        self.set_password_form = _SetPasswordForm(
            user=user,
            data={
                "password": attrs["newPassword"],
            },
        )
        if not self.set_password_form.is_valid():
            raise serializers.ValidationError(self.set_password_form.errors)

        return attrs

    def save(self):
        assert self.set_password_form
        return self.set_password_form.save()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=cast(int, get_username_max_length()),
        min_length=allauth_account_settings.USERNAME_MIN_LENGTH,
        required=allauth_account_settings.USERNAME_REQUIRED,
    )
    email = serializers.EmailField(required=allauth_account_settings.EMAIL_REQUIRED)
    password = serializers.CharField(write_only=True)

    def validate_username(self, username):
        username = get_adapter().clean_username(username)
        return username

    def validate_email(self, email):
        email = get_adapter().clean_email(email)
        if allauth_account_settings.UNIQUE_EMAIL:
            if email and email_address_exists(email):
                raise serializers.ValidationError(
                    _("A user is already registered with this e-mail address."),
                )
        return email

    def validate_password(self, password):
        return get_adapter().clean_password(password)

    def get_cleaned_data(self):
        return {
            "username": self.validated_data.get("username", ""),
            "password": self.validated_data.get("password", ""),
            "email": self.validated_data.get("email", ""),
        }

    def save(self, request):
        adapter = get_adapter()
        user = adapter.new_user(request)
        self.cleaned_data = self.get_cleaned_data()
        user = adapter.save_user(request, user, self, commit=False)
        if "password" in self.cleaned_data:
            try:
                adapter.clean_password(self.cleaned_data["password"], user=user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(
                    detail=serializers.as_serializer_error(exc)
                )
        user.save()
        setup_user_email(request, user, [])
        return user
