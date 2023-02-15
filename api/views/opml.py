import xmlschema
from defusedxml.ElementTree import ParseError as defused_ParseError
from defusedxml.ElementTree import fromstring as defused_fromstring
from django.db import transaction
from lxml import etree as lxml_etree
from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from url_normalize import url_normalize

from api import archived_feed_entry_util
from api import opml as opml_util
from api.models import (
    Feed,
    FeedSubscriptionProgressEntry,
    FeedSubscriptionProgressEntryDescriptor,
    SubscribedFeedUserMapping,
    UserCategory,
)
from api.responses import XMLResponse


class OPMLView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        user_category_text_dict = dict(
            user_category_tuple
            for user_category_tuple in request.user.user_categories.values_list(
                "uuid", "text"
            )
        )

        category_dict = request.user.category_dict()

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

        return XMLResponse(opml_element)

    def post(self, request: Request):
        opml_element: xmlschema.XMLResource
        try:
            opml_element = defused_fromstring(request.body)
        except defused_ParseError:
            raise ParseError("XML malformed")

        try:
            opml_util.schema().validate(opml_element)
        except xmlschema.XMLSchemaException:
            raise ParseError("OPML malformed")

        outline_dict: dict[str, set[tuple[str, str]]] = {}

        for outer_outline_element in opml_element.findall("./body/outline"):
            outer_outline_name = outer_outline_element.attrib["title"]

            if outer_outline_name not in outline_dict:
                outline_dict[outer_outline_name] = set()

            for outline_element in outer_outline_element.findall("./outline"):
                outline_name = outline_element.attrib["title"]
                outline_xml_url = url_normalize(outline_element.attrib["xmlUrl"])

                outline_dict[outer_outline_name].add((outline_name, outline_xml_url))

        existing_subscriptions: set[str] = set(
            SubscribedFeedUserMapping.objects.filter(user=request.user).values_list(
                "feed__feed_url", flat=True
            )
        )

        existing_categories: dict[str, UserCategory] = {
            user_category.text: user_category
            for user_category in UserCategory.objects.filter(user=request.user)
        }

        existing_category_mappings: dict[str, set[str]] = {}
        for (
            feed_user_category_mapping
        ) in Feed.user_categories.through.objects.select_related(
            "feed", "usercategory"
        ).filter(
            usercategory__user=request.user
        ):
            if (
                feed_user_category_mapping.usercategory.text
                not in existing_category_mappings
            ):
                existing_category_mappings[
                    feed_user_category_mapping.usercategory.text
                ] = set()

            existing_category_mappings[
                feed_user_category_mapping.usercategory.text
            ].add(feed_user_category_mapping.feed.feed_url)

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
                                FeedSubscriptionProgressEntry(user=request.user)
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
        feed_user_category_mappings: list[Feed.user_categories.through] = []

        for outer_outline_name, outline_set in outline_dict.items():
            user_category = existing_categories.get(outer_outline_name)
            if user_category is None:
                user_category = UserCategory(user=request.user, text=outer_outline_name)
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
                            feed=feed, user=request.user, custom_feed_title=custom_title
                        )
                        subscribed_feed_user_mappings.append(
                            subscribed_feed_user_mapping
                        )
                        existing_subscriptions.add(outline_xml_url)

                    if outline_xml_url not in existing_category_mapping_set:
                        feed_user_category_mapping = Feed.user_categories.through(
                            feed=feed, usercategory=user_category
                        )
                        feed_user_category_mappings.append(feed_user_category_mapping)
                        existing_category_mapping_set.add(outline_xml_url)

        with transaction.atomic():
            for user_category in user_categories:
                user_category.save()

            SubscribedFeedUserMapping.objects.bulk_create(subscribed_feed_user_mappings)
            Feed.user_categories.through.objects.bulk_create(
                feed_user_category_mappings
            )

            for feed in feeds_dict.values():
                if feed is not None:
                    archived_feed_entry_util.mark_archived_entries(
                        archived_feed_entry_util.read_mapping_generator_fn(
                            feed, request.user
                        )
                    )

            if feed_subscription_progress_entry is not None:
                feed_subscription_progress_entry.save()

                FeedSubscriptionProgressEntryDescriptor.objects.bulk_create(
                    feed_subscription_progress_entry_descriptors
                )

        if feed_subscription_progress_entry is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(
                str(feed_subscription_progress_entry.uuid),
                status=status.HTTP_202_ACCEPTED,
            )