from collections import defaultdict
from typing import Iterable, NamedTuple, cast
from xml.etree.ElementTree import Element

import lxml.etree as lxml_etree
import xmlschema
from defusedxml.ElementTree import ParseError as defused_ParseError
from defusedxml.ElementTree import fromstring as defused_fromstring
from django.db import transaction
from django.http.response import HttpResponse
from drf_yasg import openapi
from drf_yasg.inspectors import SwaggerAutoSchema
from drf_yasg.utils import swagger_auto_schema
from rest_framework.exceptions import ParseError, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api import grace_period_util
from api import opml as opml_util
from api.models import (
    Feed,
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
    ReadFeedEntryUserMapping,
    SubscribedFeedUserMapping,
    User,
    UserCategory,
)
from api.negotiation import IgnoreClientContentNegotiation


class _OPMLGetSwaggerAutoSchema(SwaggerAutoSchema):  # pragma: no cover
    def get_consumes(self):
        return ["text/xml"]

    def get_produces(self):
        return ["text/xml"]


class OPMLView(APIView):
    content_negotiation_class = IgnoreClientContentNegotiation

    @swagger_auto_schema(
        auto_schema=_OPMLGetSwaggerAutoSchema,
        responses={200: "OPML XML"},
        operation_summary="Download your OPML file",
        operation_description="""Download your OPML file.

This will return [OPML](http://opml.org/spec2.opml) XML representing your subscribed feeds.""",
    )
    def get(self, request: Request):
        user_category_text_dict = dict(
            user_category_tuple
            for user_category_tuple in UserCategory.objects.filter(
                user=cast(User, request.user)
            ).values_list("uuid", "text")
        )

        category_dict = cast(User, request.user).category_dict()

        opml_element = lxml_etree.Element("opml", version="1.0")
        head_element = lxml_etree.SubElement(opml_element, "head")
        title_element = lxml_etree.SubElement(head_element, "title")
        title_element.text = "RSS Temple OMPL"
        body_element = lxml_etree.SubElement(opml_element, "body")

        for uuid_, feeds in category_dict.items():
            outer_outline_name = (
                user_category_text_dict[uuid_]
                if uuid_ is not None
                else "Not Categorized"
            )

            outer_outline_element = lxml_etree.SubElement(
                body_element,
                "outline",
                text=outer_outline_name,
                title=outer_outline_name,
            )

            for feed in feeds:
                title = feed.title
                custom_title = feed.custom_title
                outline_name = custom_title if custom_title is not None else title
                assert feed.home_url is not None
                lxml_etree.SubElement(
                    outer_outline_element,
                    "outline",
                    type="rss",
                    text=outline_name,
                    title=outline_name,
                    xmlUrl=feed.feed_url,
                    htmlUrl=feed.home_url,
                )

        return HttpResponse(lxml_etree.tostring(opml_element), content_type="text/xml")

    @swagger_auto_schema(
        request_body=openapi.Schema(type="string"),
        responses={202: openapi.Schema(type="string"), 204: ""},
        operation_summary="Download your OPML file",
        operation_description="""Download your OPML file.

This will return [OPML](http://opml.org/spec2.opml) XML representing your subscribed feeds.""",
    )
    def post(self, request: Request):
        user = cast(User, request.user)

        opml_element: Element
        try:
            opml_element = defused_fromstring(request.body)
        except defused_ParseError as e:
            raise ParseError(e.msg)

        try:
            opml_util.schema().validate(opml_element)
        except xmlschema.XMLSchemaException as e:
            raise ValidationError({".": str(e)})

        grouped_entries = opml_util.get_grouped_entries(opml_element)

        existing_subscriptions: set[str] = set(
            user.subscribed_feeds.values_list("feed_url", flat=True)
        )

        existing_user_categories: dict[str, UserCategory] = {
            user_category.text: user_category
            for user_category in user.user_categories.all()
        }

        existing_category_name_to_urls_mappings: dict[str, set[str]] = defaultdict(set)
        for user_category in existing_user_categories.values():
            for feed in cast(Iterable[Feed], user_category.feeds.all()):
                existing_category_name_to_urls_mappings[user_category.text].add(
                    feed.feed_url
                )

        (
            feeds_dict,
            feed_subscription_progress_entry,
            feed_subscription_progress_entry_descriptors,
        ) = OPMLView._get_or_create_feeds(user, grouped_entries)

        (
            user_categories,
            subscribed_feed_user_mappings,
            feed_url_user_categories,
        ) = OPMLView._create_subscriptions_and_caregories(
            user,
            grouped_entries,
            existing_user_categories,
            existing_category_name_to_urls_mappings,
            existing_subscriptions,
            feeds_dict,
        )

        with transaction.atomic():
            for user_category in user_categories:
                user_category.save()

            SubscribedFeedUserMapping.objects.bulk_create(subscribed_feed_user_mappings)
            for feed_url, user_categories_ in feed_url_user_categories.items():
                if (feed_ := feeds_dict[feed_url]) is not None:
                    feed_.user_categories.add(*user_categories_)

            for feed_ in feeds_dict.values():
                if feed_ is not None:
                    ReadFeedEntryUserMapping.objects.bulk_create(
                        grace_period_util.generate_grace_period_read_entries(
                            feed_, cast(User, request.user)
                        ),
                        ignore_conflicts=True,
                    )

            if feed_subscription_progress_entry is not None:
                feed_subscription_progress_entry.save()

                FeedSubscriptionProgressEntryDescriptor.objects.bulk_create(
                    feed_subscription_progress_entry_descriptors
                )

        return (
            Response(status=204)
            if feed_subscription_progress_entry is None
            else Response(str(feed_subscription_progress_entry.uuid), status=202)
        )

    class _GetFeedsOutput(NamedTuple):
        feeds_dict: dict[str, Feed | None]
        feed_subscription_progress_entry: FeedSubscriptionProgressEntry | None
        feed_subscription_progress_entry_descriptors: list[
            FeedSubscriptionProgressEntryDescriptor
        ]

    @classmethod
    def _get_or_create_feeds(
        cls, user: User, grouped_entries: dict[str | None, frozenset[opml_util.Entry]]
    ) -> _GetFeedsOutput:
        feeds_dict: dict[str, Feed | None] = {
            f.feed_url: f
            for f in Feed.objects.filter(
                feed_url__in=frozenset(
                    t.url for e in grouped_entries.values() for t in e
                )
            )
        }

        feed_subscription_progress_entry: FeedSubscriptionProgressEntry | None = None
        feed_subscription_progress_entry_descriptors: list[
            FeedSubscriptionProgressEntryDescriptor
        ] = []

        for group_name, entries in grouped_entries.items():
            for title, url in entries:
                if url not in feeds_dict:
                    if feed_subscription_progress_entry is None:
                        feed_subscription_progress_entry = (
                            FeedSubscriptionProgressEntry(user=user)
                        )

                    feed_subscription_progress_entry_descriptors.append(
                        FeedSubscriptionProgressEntryDescriptor(
                            feed_subscription_progress_entry=feed_subscription_progress_entry,
                            feed_url=url,
                            custom_feed_title=title,
                            user_category_text=group_name,
                        )
                    )

                    feeds_dict[url] = None

        return cls._GetFeedsOutput(
            feeds_dict,
            feed_subscription_progress_entry,
            feed_subscription_progress_entry_descriptors,
        )

    class _GetSubscriptionMappingsOutput(NamedTuple):
        user_categories: list[UserCategory]
        subscribed_feed_user_mappings: list[SubscribedFeedUserMapping]
        feed_url_user_categories: dict[str, list[UserCategory]]

    @classmethod
    def _create_subscriptions_and_caregories(
        cls,
        user: User,
        grouped_entries: dict[str | None, frozenset[opml_util.Entry]],
        existing_user_categories: dict[str, UserCategory],
        existing_category_name_to_urls_mappings: dict[str, set[str]],
        existing_subscriptions: set[str],
        feeds_dict: dict[str, Feed | None],
    ) -> _GetSubscriptionMappingsOutput:
        user_categories: list[UserCategory] = []
        subscribed_feed_user_mappings: list[SubscribedFeedUserMapping] = []
        feed_url_user_categories: dict[str, list[UserCategory]] = defaultdict(list)

        for group_name, entries in grouped_entries.items():
            if group_name is not None:
                user_category = existing_user_categories.get(group_name)
                if user_category is None:
                    user_category = UserCategory(user=user, text=group_name)
                    user_categories.append(user_category)
                    existing_user_categories[user_category.text] = user_category

                category_urls = existing_category_name_to_urls_mappings[group_name]

                for title, url in entries:
                    if url not in category_urls:
                        feed_url_user_categories[url].append(user_category)
                        category_urls.add(url)

            for title, url in entries:
                feed = feeds_dict[url]
                if feed is not None:
                    custom_title = title if title != feed.title else None

                    if url not in existing_subscriptions:
                        subscribed_feed_user_mapping = SubscribedFeedUserMapping(
                            feed=feed,
                            user=user,
                            custom_feed_title=custom_title,
                        )
                        subscribed_feed_user_mappings.append(
                            subscribed_feed_user_mapping
                        )
                        existing_subscriptions.add(url)

        return cls._GetSubscriptionMappingsOutput(
            user_categories, subscribed_feed_user_mappings, feed_url_user_categories
        )
