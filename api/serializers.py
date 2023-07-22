from dj_rest_auth.serializers import UserDetailsSerializer as _UserDetailsSerializer
from rest_framework import serializers

from api.models import User


class UserDetailsSerializer(serializers.ModelSerializer):
    subscribedFeedUuids = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True, source="subscribed_feeds"
    )

    class Meta(_UserDetailsSerializer.Meta):
        model = User
        fields = ("uuid", "email", "subscribedFeedUuids", "attributes")
        read_only_fields = ("uuid", "email", "attributes")
