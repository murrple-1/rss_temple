from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db.utils import IntegrityError
from django.db import transaction

from lxml import etree as lxml_etree

from defusedxml.ElementTree import fromstring as defused_fromstring, ParseError as defused_ParseError

import xmlschema

from api import models, searchqueries, feed_handler, opml as opml_util
from api.exceptions import QueryException
from api.context import Context


def opml(request):
    permitted_methods = {'GET', 'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _opml_get(request)
    elif request.method == 'POST':
        return _opml_post(request)


def _opml_get(request):
    category_dict = request.user.category_dict()

    opml_element = lxml_etree.Element('opml', version='1.0')
    head_element = lxml_etree.SubElement(opml_element, 'head')
    title_element = lxml_etree.SubElement(head_element, 'title')
    title_element.text = 'RSS Temple OMPL'
    body_element = lxml_etree.SubElement(opml_element, 'body')

    for key, feeds in category_dict.items():
        outer_outline_name = key if key is not None else 'Not Categorized'

        outer_outline_element = lxml_etree.SubElement(body_element, 'outline', text=outer_outline_name, title=outer_outline_name)

        for feed in feeds:
            outline_name = feed._custom_title if feed._custom_title is not None else feed.title
            lxml_etree.SubElement(outer_outline_element, 'outline',
                type='rss', text=outline_name, title=outline_name, xmlUrl=feed.feed_url, htmlUrl=feed.home_url)

    return HttpResponse(lxml_etree.tostring(opml_element), 'text/xml')


def _opml_post(request):
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

    for outer_outline_element in opml_element.findall('./body/outline'):
        outer_outline_name = outer_outline_element.attrib['title']

        for outline_element in outer_outline_element.findall('./outline'):
            outline_name = outline_element.attrib['title']

            outline_xml_url = outline_element.attrib['xmlUrl']

            # TODO build feeds

    # TODO finish

    return HttpResponse()
