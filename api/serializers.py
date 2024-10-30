import logging
import re
import uuid
from typing import Any, cast

from allauth.account.adapter import get_adapter
from allauth.account.forms import PasswordVerificationMixin, SetPasswordField, UserForm
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from dj_rest_auth.app_settings import api_settings
from dj_rest_auth.registration.serializers import (
    SocialLoginSerializer as SocialLoginSerializer_,
)
from dj_rest_auth.serializers import LoginSerializer as _LoginSerializer
from dj_rest_auth.serializers import UserDetailsSerializer as _UserDetailsSerializer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import OrderBy, Q
from django.db.models.functions import Now
from django.http.request import HttpRequest
from django.http.response import HttpResponseBadRequest
from django.urls import exceptions as url_exceptions
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from requests.exceptions import HTTPError
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.request import Request

try:
    from allauth.account import app_settings as allauth_account_settings
    from allauth.account.adapter import get_adapter
    from allauth.account.utils import setup_user_email
    from allauth.socialaccount.helpers import complete_social_login
    from allauth.utils import email_address_exists, get_username_max_length
except ImportError:  # pragma: no cover
    raise ImportError("allauth needs to be added to INSTALLED_APPS.")

from api.exceptions import Conflict, UnprocessableContent
from api.fields import field_configs
from api.models import Captcha, ClassifierLabel, Feed, User, UserCategory
from api.searches import search_fns
from api.sorts import sort_configs
from query_utils import fields as fieldutils
from query_utils import search as searchutils
from query_utils import sort as sortutils

_logger = logging.getLogger("rss_temple")


class LoginSerializer(_LoginSerializer):  # pragma: no cover
    stayLoggedIn = serializers.BooleanField(source="stay_logged_in")

    def get_auth_user(self, username, email, password):
        if "allauth" in settings.INSTALLED_APPS:
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

        self.validate_auth_user_status(user)

        if "dj_rest_auth.registration" in settings.INSTALLED_APPS:
            self.validate_email_verification_status(user, email=email)

        attrs["user"] = user
        return attrs


class UserDetailsSerializer(serializers.ModelSerializer[User]):  # pragma: no cover
    subscribedFeedUuids: "serializers.PrimaryKeyRelatedField[Feed]" = (
        serializers.PrimaryKeyRelatedField(
            many=True, read_only=True, source="subscribed_feeds"
        )
    )

    class Meta(_UserDetailsSerializer.Meta):
        model = User
        fields = ("uuid", "email", "subscribedFeedUuids", "attributes")
        read_only_fields = ("uuid", "email", "attributes")


class _SetPasswordForm(PasswordVerificationMixin, UserForm):  # pragma: no cover
    password = SetPasswordField()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        setattr(self.fields["password"], "user", self.user)

    def save(self):
        get_adapter().set_password(self.user, self.cleaned_data["password"])


# based on `dj_rest_auth.serializers.PasswordChangeSerializer`
class PasswordChangeSerializer(serializers.Serializer):  # pragma: no cover
    oldPassword = serializers.CharField(max_length=128)
    newPassword = serializers.CharField(max_length=128)

    set_password_form: _SetPasswordForm | None = None

    request: HttpRequest

    def __init__(self, *args: Any, **kwargs: Any):
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

            assert isinstance(self.request.user, AbstractBaseUser)
            update_session_auth_hash(self.request, self.request.user)


# based on `dj_rest_auth.serializers.PasswordResetConfirmSerializer`
class PasswordResetConfirmSerializer(serializers.Serializer):  # pragma: no cover
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


# based on `dj_rest_auth.registration.serializers.RegisterSerializer`
class RegisterSerializer(serializers.Serializer):  # pragma: no cover
    username = serializers.CharField(
        max_length=cast(int, get_username_max_length()),
        min_length=allauth_account_settings.USERNAME_MIN_LENGTH,
        required=allauth_account_settings.USERNAME_REQUIRED,
    )
    email = serializers.EmailField(required=allauth_account_settings.EMAIL_REQUIRED)
    password = serializers.CharField(write_only=True)
    captcha = serializers.CharField(write_only=True)

    def validate_username(self, username):
        username = get_adapter().clean_username(username)
        return username

    def validate_email(self, email):
        email = get_adapter().clean_email(email)
        if allauth_account_settings.UNIQUE_EMAIL:
            if email and email_address_exists(email):
                raise Conflict(
                    "A user is already registered with this e-mail address.",
                )
        return email

    def validate_password(self, password):
        return get_adapter().clean_password(password)

    def validate_captcha(self, captcha_str):
        if (
            match := re.search(r"^([A-Za-z0-9_\-]{43}):([A-Za-z0-9]+)$", captcha_str)
        ) is None:
            raise serializers.ValidationError({"captcha": "malformed"})

        captcha_key: str = match.group(1)
        captcha_secret_phrase: str = match.group(2)

        captcha: Captcha
        try:
            captcha = Captcha.objects.get(key=captcha_key, expires_at__gt=Now())
        except Captcha.DoesNotExist:
            raise NotFound("captcha not found")

        if captcha.secret_phrase.lower() != captcha_secret_phrase.lower():
            captcha.delete()
            raise UnprocessableContent({"captchaSecretPhrase": "incorrect"})

        return captcha_str

    def get_cleaned_data(self):
        return {
            "username": self.validated_data.get("username", ""),
            "password1": self.validated_data.get(  # `password1` is used by the adapter
                "password", ""
            ),
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


class SocialLoginSerializer(SocialLoginSerializer_):  # pragma: no cover
    stayLoggedIn = serializers.BooleanField(source="stay_logged_in")

    # copy-paste of `SocialLoginSerializer_.validate()`, but I wanted
    # the exception raised if `account_exists` to be different than
    # the original implementation
    def validate(self, attrs):
        view = self.context.get("view")
        request = self._get_request()

        if not view:
            raise serializers.ValidationError(
                _("View is not defined, pass it as a context variable"),
            )

        adapter_class = getattr(view, "adapter_class", None)
        if not adapter_class:
            raise serializers.ValidationError(_("Define adapter_class in view"))

        adapter = adapter_class(request)
        app = adapter.get_provider().get_app(request)

        # More info on code vs access_token
        # http://stackoverflow.com/questions/8666316/facebook-oauth-2-0-code-and-token

        access_token = attrs.get("access_token")
        code = attrs.get("code")
        # Case 1: We received the access_token
        if access_token:
            tokens_to_parse = {"access_token": access_token}
            token = access_token
            # For sign in with apple
            id_token = attrs.get("id_token")
            if id_token:
                tokens_to_parse["id_token"] = id_token

        # Case 2: We received the authorization code
        elif code:
            self.set_callback_url(view=view, adapter_class=adapter_class)
            self.client_class = getattr(view, "client_class", None)

            if not self.client_class:
                raise serializers.ValidationError(
                    _("Define client_class in view"),
                )

            provider = adapter.get_provider()
            scope = provider.get_scope(request)
            client = self.client_class(
                request,
                app.client_id,
                app.secret,
                adapter.access_token_method,
                adapter.access_token_url,
                self.callback_url,
                scope,
                scope_delimiter=adapter.scope_delimiter,
                headers=adapter.headers,
                basic_auth=adapter.basic_auth,
            )
            try:
                token = client.get_access_token(code)
            except OAuth2Error as ex:
                raise serializers.ValidationError(
                    _("Failed to exchange code for access token")
                ) from ex
            access_token = token["access_token"]
            tokens_to_parse = {"access_token": access_token}

            # If available we add additional data to the dictionary
            for key in ["refresh_token", "id_token", adapter.expires_in_key]:
                if key in token:
                    tokens_to_parse[key] = token[key]
        else:
            raise serializers.ValidationError(
                _("Incorrect input. access_token or code is required."),
            )

        social_token = adapter.parse_token(tokens_to_parse)
        social_token.app = app

        try:
            if adapter.provider_id == "google" and not code:
                login = self.get_social_login(
                    adapter, app, social_token, response={"id_token": token}
                )
            else:
                login = self.get_social_login(adapter, app, social_token, token)
            ret = complete_social_login(request, login)
        except HTTPError:
            raise serializers.ValidationError(_("Incorrect value"))

        if isinstance(ret, HttpResponseBadRequest):
            raise serializers.ValidationError(
                ret.content.decode("utf-8", errors="replace")
            )

        if not login.is_existing:
            # We have an account already signed up in a different flow
            # with the same email address: raise an exception.
            # This needs to be handled in the frontend. We can not just
            # link up the accounts due to security constraints
            if allauth_account_settings.UNIQUE_EMAIL:
                # Do we have an account already with this email address?
                account_exists = (
                    get_user_model()
                    .objects.filter(
                        email=login.user.email,
                    )
                    .exists()
                )
                if account_exists:
                    raise UnprocessableContent(
                        {
                            "details": "User is already registered with this e-mail address."
                        },
                    )

            login.lookup()
            login.save(request, connect=True)
            self.post_signup(login, attrs)

        attrs["user"] = login.account.user

        return attrs


class UserDeleteSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)


class _FieldsField(serializers.ListField):
    def __init__(self, *args: Any, **kwargs: Any):
        kwargs["child"] = serializers.CharField()
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data: Any):
        data = super().to_internal_value(data)

        data = sorted(frozenset(data))

        object_name: str | None = self.context.get("object_name")
        if not object_name:  # pragma: no cover
            return []

        if settings.DEBUG and len(data) == 1 and data[0] == "_all":
            field_maps = fieldutils.get_all_field_maps(object_name, field_configs)
        else:
            field_maps = []
            for field_name in data:
                field_map = fieldutils.to_field_map(
                    object_name, field_name, field_configs
                )
                if field_map:
                    field_maps.append(field_map)

            if len(field_maps) < 1:
                field_maps = fieldutils.get_default_field_maps(
                    object_name, field_configs
                )

        return field_maps

    def get_default(self):
        object_name: str | None = self.context.get("object_name")
        if not object_name:  # pragma: no cover
            return []

        return fieldutils.get_default_field_maps(object_name, field_configs)


@extend_schema_field(
    component_name="SortField",
    field=OpenApiTypes.STR,
)
class _SortField(serializers.Field):
    def get_default(self):
        object_name: str | None = self.context.get("object_name")
        if not object_name:  # pragma: no cover
            return []

        try:
            default_sort_enabled = not self.parent.initial_data.get(
                "disableDefaultSort"
            )
        except AttributeError:  # pragma: no cover
            _logger.exception("unable to load `default_sort_enabled`. defaulting...")
            default_sort_enabled = True

        sort_list = sortutils.to_sort_list(
            object_name, None, default_sort_enabled, sort_configs
        )
        return sortutils.sort_list_to_order_by_args(
            object_name, sort_list, sort_configs
        )

    def to_internal_value(self, data: Any):
        object_name: str | None = self.context.get("object_name")
        if not object_name:  # pragma: no cover
            return []

        if isinstance(data, bool) or not isinstance(
            data,
            (
                str,
                int,
                float,
            ),
        ):
            raise serializers.ValidationError("Not a valid string.")
        data = str(data).strip()
        assert isinstance(data, str)

        try:
            default_sort_enabled = not self.parent.initial_data.get(
                "disableDefaultSort"
            )
        except AttributeError:  # pragma: no cover
            _logger.exception("unable to load `default_sort_enabled`. defaulting...")
            default_sort_enabled = True

        try:
            sort_list = sortutils.to_sort_list(
                object_name, data, default_sort_enabled, sort_configs
            )
            return sortutils.sort_list_to_order_by_args(
                object_name, sort_list, sort_configs
            )
        except (ValueError, AttributeError) as e:
            raise serializers.ValidationError("sort malformed") from e

    def to_representation(self, value: list[OrderBy]):  # pragma: no cover
        return value


@extend_schema_field(
    component_name="SearchField",
    field=OpenApiTypes.STR,
)
class _SearchField(serializers.Field):
    def get_default(self):
        return []

    def to_internal_value(self, data: Any):
        if isinstance(data, bool) or not isinstance(
            data,
            (
                str,
                int,
                float,
            ),
        ):
            raise serializers.ValidationError("Not a valid string.")
        data = str(data).strip()

        request: Request | None = self.context.get("request")
        object_name: str | None = self.context.get("object_name")
        if not request or not object_name:  # pragma: no cover
            return []

        try:
            return searchutils.to_filter_args(object_name, request, data, search_fns)
        except (ValueError, AttributeError) as e:
            raise serializers.ValidationError("search malformed") from e

    def to_representation(self, value: list[Q]):  # pragma: no cover
        return value


class GetSingleSerializer(serializers.Serializer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["fields"] = _FieldsField(required=False)


class GetManySerializer(serializers.Serializer):
    count = serializers.IntegerField(
        max_value=1000, min_value=0, default=50, required=False
    )
    skip = serializers.IntegerField(min_value=0, default=0, required=False)
    objects = serializers.BooleanField(
        default=True, required=False, source="return_objects"
    )
    totalCount = serializers.BooleanField(
        default=True, required=False, source="return_total_count"
    )
    sort = _SortField(required=False)
    search = _SearchField(required=False)
    disableDefaultSort = serializers.BooleanField(
        default=False, required=False, source="disable_default_sort"
    )

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["fields"] = _FieldsField(required=False)


class QuerySerializer(serializers.Serializer):
    totalCount = serializers.IntegerField(required=False)
    objects = serializers.ListField(child=serializers.DictField(), required=False)


class StableQueryCreateSerializer(serializers.Serializer):
    sort = _SortField(required=False)
    search = _SearchField(required=False)
    disableDefaultSort = serializers.BooleanField(
        default=False, required=False, source="disable_default_sort"
    )

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["fields"] = _FieldsField(required=False)


def _token_validate(data: Any):
    if isinstance(data, str) and re.search(r"^[a-z_]+-\d+$", data) is None:
        raise serializers.ValidationError("malformed")


class StableQueryMultipleSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, validators=[_token_validate])
    count = serializers.IntegerField(
        max_value=1000, min_value=0, default=50, required=False
    )
    skip = serializers.IntegerField(min_value=0, default=0, required=False)
    objects = serializers.BooleanField(
        default=True, required=False, source="return_objects"
    )
    totalCount = serializers.BooleanField(
        default=True, required=False, source="return_total_count"
    )
    sort = _SortField(required=False)
    search = _SearchField(required=False)
    disableDefaultSort = serializers.BooleanField(
        default=False, required=False, source="disable_default_sort"
    )

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["fields"] = _FieldsField(required=False)


class FeedGetSerializer(serializers.Serializer):
    url = serializers.URLField(required=True)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["fields"] = _FieldsField(required=False)


class FeedFindQuerySerializer(serializers.Serializer):
    url = serializers.URLField(required=True)


class FeedFindSerializer(serializers.Serializer):
    title = serializers.CharField(read_only=True)
    href = serializers.URLField(read_only=True)


class FeedSubscribeSerializer(serializers.Serializer):
    url = serializers.URLField(required=True)
    customTitle = serializers.CharField(required=False, source="custom_title")


class UserCategoryCreateSerializer(serializers.Serializer):
    text = serializers.CharField(required=True)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["fields"] = _FieldsField(required=False)


class FeedEntriesMarkSerializer(serializers.Serializer):
    feedEntryUuids = serializers.ListField(
        child=serializers.UUIDField(), required=True, source="feed_entry_uuids"
    )


class FeedEntriesMarkReadSerializer(serializers.Serializer):
    feedUuids = serializers.ListField(
        child=serializers.UUIDField(), required=False, source="feed_uuids"
    )
    feedEntryUuids = serializers.ListField(
        child=serializers.UUIDField(), required=False, source="feed_entry_uuids"
    )


class FeedEntryLanguagesQuerySerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        ("iso639_1", "iso639_3", "name"), default="iso639_3", required=False
    )


class FeedEntryLanguagesSerializer(serializers.Serializer):
    languages = serializers.ListField(child=serializers.CharField())


class UserCategorySerializer(serializers.ModelSerializer[UserCategory]):
    class Meta:
        model = UserCategory
        fields = ("text",)


class UserCategoryApplySerializer(serializers.Serializer):
    mappings = serializers.DictField(
        child=serializers.ListField(child=serializers.UUIDField())
    )

    def validate_mappings(self, mappings: dict[str, list[uuid.UUID]]):
        validated_mappings: dict[uuid.UUID, frozenset[uuid.UUID]] = {}
        for feed_uuid, user_category_uuids in mappings.items():
            feed_uuid_: uuid.UUID
            try:
                feed_uuid_ = uuid.UUID(feed_uuid)
            except ValueError:
                raise serializers.ValidationError("key malformed")

            validated_mappings[feed_uuid_] = frozenset(user_category_uuids)

        return validated_mappings


class _ExploreFeedSerializer(serializers.Serializer):
    class Meta:
        ref_name = "ExploreFeed"

    name = serializers.CharField()
    feedUrl = serializers.URLField()
    homeUrl = serializers.URLField()
    imageSrc = serializers.URLField()
    entryTitles = serializers.ListField(child=serializers.CharField())
    isSubscribed = serializers.BooleanField()


class ExploreSerializer(serializers.Serializer):
    tagName = serializers.CharField()
    feeds = _ExploreFeedSerializer(many=True)


class ClassifierLabelListQuerySerializer(serializers.Serializer):
    feedEntryUuid = serializers.UUIDField(required=False, source="feed_entry_uuid")


class ClassifierLabelSerializer(serializers.ModelSerializer[ClassifierLabel]):
    class Meta:
        model = ClassifierLabel
        fields = "__all__"


class ClassifierLabelListByEntryBodySerializer(serializers.Serializer):
    feedEntryUuids = serializers.ListField(
        child=serializers.UUIDField(), required=True, source="feed_entry_uuids"
    )


class ClassifierLabelListByEntrySerializer(serializers.Serializer):
    classifierLabels = serializers.DictField(
        child=serializers.ListField(child=ClassifierLabelSerializer()),
        source="classifier_labels",
    )


class ClassifierLabelVotesListQuerySerializer(serializers.Serializer):
    count = serializers.IntegerField(
        max_value=1000, min_value=0, default=50, required=False
    )
    skip = serializers.IntegerField(min_value=0, default=0, required=False)


class ClassifierLabelVotesSerializer(serializers.Serializer):
    feedEntryUuid = serializers.UUIDField(read_only=True, source="feed_entry_uuid")
    classifierLabelUuids = serializers.ListField(
        child=serializers.UUIDField(), source="classifier_label_uuids"
    )


class _ClassifierLabelVotesSerializer(serializers.Serializer):
    feedEntryUuid = serializers.UUIDField(read_only=True)
    classifierLabelUuids = serializers.ListField(
        read_only=True, child=serializers.UUIDField()
    )


class ClassifierLabelVotesListSerializer(serializers.Serializer):
    objects = _ClassifierLabelVotesSerializer(many=True, read_only=True)
    totalCount = serializers.IntegerField(read_only=True)
