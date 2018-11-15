from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db.utils import IntegrityError
from django.db import transaction

from lxml import etree

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
    # TODO write
    opml_element = etree.Element('opml', version='1.0')
    head_element = etree.SubElement(opml_element, 'head')
    title_element = etree.SubElement(head_element, 'title')
    title_element.text = 'Murray subscriptions in feedly Cloud'
    body_element = etree.SubElement(opml_element, 'body')

    outer_outline_element = etree.SubElement(body_element, 'outline', text='Gaming', title='Gaming')

    etree.SubElement(outer_outline_element, 'outline',
        type='rss', text='Kotaku', title='Kotaku', xmlUrl='http://feeds.gawker.com/kotaku/full', htmlUrl='https://kotaku.com')
    etree.SubElement(outer_outline_element, 'outline',
        type='rss', text='Gamasutra Feature Articles', title='Gamasutra Feature Articles', xmlUrl='http://feeds.feedburner.com/GamasutraFeatureArticles', htmlUrl='http://www.gamasutra.com/newswire')

    return HttpResponse(etree.tostring(opml_element), 'text/xml')


def _opml_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    opml_element = None
    try:
        opml_element = etree.fromstring(request.body)
    except etree.XMLSyntaxError:
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    try:
        opml_util.schema().validate(opml_element)
    except xmlschema.XMLSchemaException:
        return HttpResponseBadRequest('OPML not valid')

    # TODO finish

    return HttpResponse()
