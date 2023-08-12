from collections import defaultdict
from typing import cast
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
from rest_framework import permissions
from rest_framework.exceptions import ParseError, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from url_normalize import url_normalize

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
    permission_classes = (permissions.IsAuthenticated,)
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
        opml_element: Element
        try:
            opml_element = defused_fromstring(request.body)
        except defused_ParseError:
            raise ParseError

        try:
            opml_util.schema().validate(opml_element)
        except xmlschema.XMLSchemaException:
            raise ValidationError({".": "OPML not valid"})

        outline_dict: dict[str, set[tuple[str, str]]] = {}

        for outer_outline_element in opml_element.findall("./body/outline"):
            outer_outline_name = outer_outline_element.attrib["title"]

            if outer_outline_name not in outline_dict:
                outline_dict[outer_outline_name] = set()

            for outline_element in outer_outline_element.findall("./outline"):
                outline_name = outline_element.attrib["title"]
                outline_xml_url = cast(
                    str, url_normalize(outline_element.attrib["xmlUrl"])
                )

                outline_dict[outer_outline_name].add((outline_name, outline_xml_url))

        existing_subscriptions = set(
            SubscribedFeedUserMapping.objects.filter(
                user=cast(User, request.user)
            ).values_list("feed__feed_url", flat=True)
        )

        existing_categories = {
            user_category.text: user_category
            for user_category in UserCategory.objects.filter(
                user=cast(User, request.user)
            )
        }

        user_category: UserCategory | None
        feed: Feed | None

        existing_category_mappings: dict[str, set[str]] = defaultdict(set)
        for user_category in cast(User, request.user).user_categories.all():
            for feed in user_category.feeds.all():
                assert feed is not None
                assert user_category is not None
                existing_category_mappings[user_category.text].add(feed.feed_url)

        feeds_dict: dict[str, Feed | None] = {}

        feed_subscription_progress_entry: FeedSubscriptionProgressEntry | None = None
        feed_subscription_progress_entry_descriptors: list[
            FeedSubscriptionProgressEntryDescriptor
        ] = []

        for outer_outline_name, outline_set in outline_dict.items():
            for outline_name, outline_xml_url in outline_set:
                if outline_xml_url not in feeds_dict:
                    try:
                        feeds_dict[outline_xml_url] = Feed.objects.get(
                            feed_url=outline_xml_url
                        )
                    except Feed.DoesNotExist:
                        if feed_subscription_progress_entry is None:
                            feed_subscription_progress_entry = (
                                FeedSubscriptionProgressEntry(
                                    user=cast(User, request.user)
                                )
                            )

                        feed_subscription_progress_entry_descriptor = FeedSubscriptionProgressEntryDescriptor(
                            feed_subscription_progress_entry=feed_subscription_progress_entry,
                            feed_url=outline_xml_url,
                            custom_feed_title=outline_name,
                            user_category_text=outer_outline_name,
                        )
                        feed_subscription_progress_entry_descriptors.append(
                            feed_subscription_progress_entry_descriptor
                        )

                        feeds_dict[outline_xml_url] = None

        user_categories: list[UserCategory] = []
        subscribed_feed_user_mappings: list[SubscribedFeedUserMapping] = []
        feed_url_user_categories: dict[str, list[UserCategory]] = defaultdict(list)

        for outer_outline_name, outline_set in outline_dict.items():
            user_category = existing_categories.get(outer_outline_name)
            if user_category is None:
                user_category = UserCategory(
                    user=cast(User, request.user), text=outer_outline_name
                )
                user_categories.append(user_category)
                existing_categories[user_category.text] = user_category

            existing_category_mapping_set = existing_category_mappings.get(
                outer_outline_name
            )

            if existing_category_mapping_set is None:
                existing_category_mapping_set = set()
                existing_category_mappings[
                    outer_outline_name
                ] = existing_category_mapping_set

            for outline_name, outline_xml_url in outline_set:
                feed = feeds_dict[outline_xml_url]
                if feed is not None:
                    custom_title = outline_name if outline_name != feed.title else None

                    if outline_xml_url not in existing_subscriptions:
                        subscribed_feed_user_mapping = SubscribedFeedUserMapping(
                            feed=feed,
                            user=cast(User, request.user),
                            custom_feed_title=custom_title,
                        )
                        subscribed_feed_user_mappings.append(
                            subscribed_feed_user_mapping
                        )
                        existing_subscriptions.add(outline_xml_url)

                    if outline_xml_url not in existing_category_mapping_set:
                        feed_url_user_categories[feed.feed_url].append(user_category)
                        existing_category_mapping_set.add(outline_xml_url)

        with transaction.atomic():
            for user_category in user_categories:
                user_category.save()

            SubscribedFeedUserMapping.objects.bulk_create(subscribed_feed_user_mappings)
            for feed_url, user_categories in feed_url_user_categories.items():
                feed = feeds_dict[feed_url]
                assert feed is not None

                feed.user_categories.add(*user_categories)

            for feed in feeds_dict.values():
                if feed is not None:
                    ReadFeedEntryUserMapping.objects.bulk_create(
                        grace_period_util.generate_grace_period_read_entries(
                            feed, cast(User, request.user)
                        ),
                        ignore_conflicts=True,
                    )

            if feed_subscription_progress_entry is not None:
                feed_subscription_progress_entry.save()

                FeedSubscriptionProgressEntryDescriptor.objects.bulk_create(
                    feed_subscription_progress_entry_descriptors
                )

        if feed_subscription_progress_entry is None:
            return Response(status=204)
        else:
            return Response(str(feed_subscription_progress_entry.uuid), status=202)
