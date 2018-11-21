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
            outline_name = feed._custom_title if feed._custom_title is not None else feed.title
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

    user_categories = []

    rss_detail_tuples = set()
    for outer_outline_element in opml_element.findall('./body/outline'):
        outer_outline_name = outer_outline_element.attrib['title']

        user_category = None
        try:
            user_category = models.UserCategory.objects.get(
                user=user, text=outer_outline_name)
            user_category._is_new = False
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=user, text=outer_outline_name)
            user_category._is_new = True

        inner_rss_detail_tuples = set()

        for outline_element in outer_outline_element.findall('./outline'):
            outline_name = outline_element.attrib['title']
            outline_xml_url = outline_element.attrib['xmlUrl']

            inner_rss_detail_tuples.add((outline_name, outline_xml_url))

        user_category._feeds = []

        for name, xml_url in inner_rss_detail_tuples.difference(rss_detail_tuples):
            if models.SubscribedFeedUserMapping.objects.filter(user=user, feed__feed_url=xml_url).exists():
                continue

            feed = None
            try:
                feed = models.Feed.objects.get(feed_url=xml_url)
                feed._is_new = False
            except models.Feed.DoesNotExist:
                try:
                    feed = _generate_feed(xml_url)
                except QueryException as e:
                    return HttpResponse(e.message, status=e.httpcode)
                feed._is_new = True

            feed._custom_title_ = name if name != feed.title else None

            user_category._feeds.append(feed)

        user_categories.append(user_category)

        rss_detail_tuples.update(inner_rss_detail_tuples)

    subscribed_feed_user_mappings = []

    for user_category in user_categories:
        for feed in user_category._feeds:
            subscribed_feed_user_mapping = models.SubscribedFeedUserMapping(
                    feed=feed, user=user, custom_feed_title=feed._custom_title_, user_category=user_category)

            subscribed_feed_user_mappings.append(subscribed_feed_user_mapping)

    with transaction.atomic():
        for user_category in user_categories:
            if user_category._is_new:
                user_category.save()

            for feed in user_category._feeds:
                if feed._is_new:
                    feed.save()

                    models.FeedEntry.objects.bulk_create(feed._feed_entries)

        models.SubscribedFeedUserMapping.objects.bulk_create(
            subscribed_feed_user_mappings)

    return HttpResponse()
