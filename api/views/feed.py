from urllib.parse import unquote

import requests
from django.db import transaction
from django_filters import rest_framework as filters
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from url_normalize import url_normalize

from api import archived_feed_entry_util, feed_handler, rss_requests
from api.exceptions import Conflict
from api.filters import FeedFilter
from api.models import Feed, FeedEntry, SubscribedFeedUserMapping
from api.serializers import FeedSerializer


class FeedListView(generics.ListAPIView):
    serializer_class = FeedSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = FeedFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Feed.annotate_search_vectors(
            Feed.annotate_subscription_data(Feed.objects.all(), self.request.user)
        )


class FeedRetrieveView(generics.RetrieveAPIView):
    serializer_class = FeedSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Feed.annotate_search_vectors(
            Feed.annotate_subscription_data(Feed.objects.all(), self.request.user)
        )

    def get_object(self):
        url = _to_normalized_url(self.kwargs["url"])

        feed: Feed
        try:
            feed = self.get_queryset().get(feed_url=url)
        except Feed.DoesNotExist:
            try:
                feed = _save_feed(url)
            except requests.exceptions.RequestException:
                raise NotFound()

        return feed


class FeedSubscribeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, **kwargs):
        user = request.user

        url = _to_normalized_url(kwargs["url"])

        feed: Feed
        try:
            feed = Feed.objects.get(feed_url=url)
        except Feed.DoesNotExist:
            try:
                feed = _save_feed(url)
            except requests.exceptions.RequestException:
                raise NotFound()

        custom_title = request.GET.get("customtitle")

        existing_subscription_list = list(
            user.subscribed_feeds.values_list(
                "feed_url", "subscribedfeedusermapping__custom_feed_title"
            )
        )

        existing_feed_urls = frozenset(t[0] for t in existing_subscription_list)
        existing_custom_titles = frozenset(
            t[1] for t in existing_subscription_list if t[1] is not None
        )

        if custom_title is not None and custom_title in existing_custom_titles:
            raise Conflict("custom title already used")

        if feed.feed_url in existing_feed_urls:
            raise Conflict("user already subscribed")

        read_mapping_generator = archived_feed_entry_util.read_mapping_generator_fn(
            feed, user
        )

        with transaction.atomic():
            SubscribedFeedUserMapping.objects.create(
                user=user, feed=feed, custom_feed_title=custom_title
            )

            archived_feed_entry_util.mark_archived_entries(read_mapping_generator)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def put(self, request: Request, **kwargs):
        user = request.user

        url = _to_normalized_url(kwargs["url"])

        custom_title = request.GET.get("customtitle")

        subscribed_feed_mapping: SubscribedFeedUserMapping
        try:
            subscribed_feed_mapping = SubscribedFeedUserMapping.objects.get(
                user=user, feed__feed_url=url
            )
        except SubscribedFeedUserMapping.DoesNotExist:
            raise NotFound("not subscribed")

        if custom_title is not None:
            if (
                SubscribedFeedUserMapping.objects.exclude(
                    uuid=subscribed_feed_mapping.uuid
                )
                .filter(user=user, custom_feed_title=custom_title)
                .exists()
            ):
                raise Conflict("custom title already used")

        subscribed_feed_mapping.custom_feed_title = custom_title
        subscribed_feed_mapping.save(update_fields=["custom_feed_title"])

        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request, **kwargs):
        url = _to_normalized_url(kwargs["url"])

        count, _ = SubscribedFeedUserMapping.objects.filter(
            user=request.user, feed__feed_url=url
        ).delete()

        if count < 1:
            raise NotFound("not subscribed")

        return Response(status=status.HTTP_204_NO_CONTENT)


def _to_normalized_url(url: str):
    return url_normalize(unquote(url))


def _save_feed(url: str):
    response = rss_requests.get(url)
    response.raise_for_status()

    with transaction.atomic():
        d = feed_handler.text_2_d(response.text)
        feed = feed_handler.d_feed_2_feed(d.feed, url)
        feed.with_subscription_data()
        feed.save()

        feed_entries = []
        for d_entry in d.get("entries", []):
            feed_entry: FeedEntry
            try:
                feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
            except ValueError:  # pragma: no cover
                continue

            feed_entry.feed = feed
            feed_entries.append(feed_entry)

        FeedEntry.objects.bulk_create(feed_entries)

        return feed
