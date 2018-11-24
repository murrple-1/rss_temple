from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.db import transaction

from lxml import etree as lxml_etree

from defusedxml.ElementTree import fromstring as defused_fromstring, ParseError as defused_ParseError

import xmlschema

from api import models, feed_handler, opml as opml_util
from api.exceptions import QueryException


def opml(request):
    permitted_methods = {'GET', 'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _opml_get(request)
    elif request.method == 'POST':
        return _opml_post(request)


def _generate_feed(url):
    d = feed_handler.url_2_d(url)
    feed = feed_handler.d_feed_2_feed(d.feed, url)
    feed._feed_entries = []

    for d_entry in d.get('entries', []):
        feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
        feed_entry.feed = feed
        feed._feed_entries.append(feed_entry)

    return feed


def _opml_get(request):
    category_dict = request.user.category_dict()

    opml_element = lxml_etree.Element('opml', version='1.0')
    head_element = lxml_etree.SubElement(opml_element, 'head')
    title_element = lxml_etree.SubElement(head_element, 'title')
    title_element.text = 'RSS Temple OMPL'
    body_element = lxml_etree.SubElement(opml_element, 'body')

    for key, feeds in category_dict.items():
        outer_outline_name = key if key is not None else 'Not Categorized'

        outer_outline_element = lxml_etree.SubElement(
            body_element, 'outline', text=outer_outline_name, title=outer_outline_name)

        for feed in feeds:
            title = feed.title
            custom_title = feed.custom_title()
            outline_name = custom_title if custom_title is not None else title
            lxml_etree.SubElement(outer_outline_element, 'outline',
                                  type='rss', text=outline_name, title=outline_name, xmlUrl=feed.feed_url, htmlUrl=feed.home_url)

    return HttpResponse(lxml_etree.tostring(opml_element), 'text/xml')


def _opml_post(request):
    user = request.user

    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    opml_element = None
    try:
        opml_element = defused_fromstring(request.body)
    except defused_ParseError:
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    try:
        opml_util.schema().validate(opml_element)
    except xmlschema.XMLSchemaException:
        return HttpResponseBadRequest('OPML not valid')

    outline_dict = {}

    for outer_outline_element in opml_element.findall('./body/outline'):
        outer_outline_name = outer_outline_element.attrib['title']

        if outer_outline_name not in outline_dict:
            outline_dict[outer_outline_name] = set()

        for outline_element in outer_outline_element.findall('./outline'):
            outline_name = outline_element.attrib['title']
            outline_xml_url = outline_element.attrib['xmlUrl']

            outline_dict[outer_outline_name].add((outline_name, outline_xml_url))

    existing_subscriptions = frozenset(models.SubscribedFeedUserMapping.objects.filter(user=user).values_list('feed__feed_url', flat=True))

    existing_category_mappings = {}
    for feed_user_category_mapping in models.FeedUserCategoryMapping.objects.select_related('feed', 'user_category').filter(user_category__user=user):
        if feed_user_category_mapping.user_category.text not in existing_category_mappings:
            existing_category_mappings[feed_user_category_mapping.user_category.text] = set()

        existing_category_mappings[feed_user_category_mapping.user_category.text].add(feed.feed_url)

    feeds_dict = {}
    subscribed_feed_user_mappings = []

    for outline_set in outline_dict.values():
        for outline_name, outline_xml_url in outline_set:
            if outline_xml_url not in feeds_dict:
                feed = None
                try:
                    feed = models.Feed.objects.get(feed_url=outline_xml_url)
                    feed._is_new = False
                except models.Feed.DoesNotExist:
                    try:
                        feed = _generate_feed(outline_xml_url)
                    except QueryException as e:
                        feeds_dict[outline_xml_url] = None
                        continue

                    feed._is_new = True

                feeds_dict[outline_xml_url] = feed

                custom_title = outline_name if outline_name != feed.title else None

                if outline_xml_url not in existing_subscriptions:
                    subscribed_feed_user_mapping = models.SubscribedFeedUserMapping(
                        feed=feed, user=user, custom_feed_title=custom_title)

                    subscribed_feed_user_mappings.append(subscribed_feed_user_mapping)

    user_categories = []
    feed_user_category_mappings = []

    for outer_outline_name, outline_set in outline_dict.items():
        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=user, text=outer_outline_name)
            user_category._is_new = False
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=user, text=outer_outline_name)
            user_category._is_new = True

        user_categories.append(user_category)

        existing_category_mapping_set = existing_category_mappings.get(outer_outline_name)
        for _, outline_xml_url in outline_set:
            feed = feeds_dict[outline_xml_url]
            if feed is not None:
                if existing_category_mapping_set is None or outline_xml_url not in existing_category_mapping_set:
                    feed_user_category_mapping = models.FeedUserCategoryMapping(
                        feed=feeds_dict[outline_xml_url], user_category=user_category)
                    feed_user_category_mappings.append(feed_user_category_mapping)

    # save feeds, even if the rest fails, so we can use them for other users, or to speed up repeat attempts
    with transaction.atomic():
        for feed in feeds_dict.values():
            if feed is not None and feed._is_new:
                feed.save()

                models.FeedEntry.objects.bulk_create(feed._feed_entries)

    with transaction.atomic():
        for user_category in user_categories:
            if user_category._is_new:
                user_category.save()

        models.SubscribedFeedUserMapping.objects.bulk_create(
            subscribed_feed_user_mappings)
        models.FeedUserCategoryMapping.objects.bulk_create(
            feed_user_category_mappings)

    return HttpResponse()
