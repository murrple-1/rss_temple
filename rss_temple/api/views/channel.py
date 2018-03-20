import pprint
import logging

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound

import feedparser

import requests

from api import models, searchqueries
from api.exceptions import QueryException


_logger = None
def logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger('rss_temple')

    return _logger



_OBJECT_NAME = 'channel'


def channel(request):
    permitted_methods = ['GET']

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)

    if request.method == 'GET':
        return _channel_get(request)


def channels(request):
    permitted_methods = ['GET']

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)

    if request.method == 'GET':
        return _channels_get(request)


def __feedparse_d_to_channel(d, link):
    if 'feed' in d:
        feed = d['feed']

        channel = models.Channel()

        if 'title' in feed:
            channel.title = feed['title']
        else:
            raise QueryException('feed malformed', 401)

        if 'subtitle' in feed:
            channel.description = feed['subtitle']
        elif 'description' in feed:
            channel.description = feed['description']

        channel.link = link

        return channel
    else:
        raise QueryException('feed malformed', 401)


def _channel_get(request):
    context = searchqueries.Context()
    context.parse_query_dict(request.GET)

    link = request.GET.get('link')
    if not link:
        return HttpResponseBadRequest('\'link\' missing')

    field_maps = None
    try:
        field_maps = searchqueries.get_field_maps(request.GET, _OBJECT_NAME)
    except QueryException as e:
        return HttpResponse(e.message, status_code=e.httpcode)

    channel = None
    try:
        channel = models.Channel.objects.get(link=link)
    except models.Channel.DoesNotExist:
        channel = models.Channel()

        try:
            r = requests.get(link)

            d = feedparser.parse(r.text)

            logger().info('channel info: %s', pprint.pformat(d))

            try:
                channel = __feedparse_d_to_channel(d, link)
            except QueryException as e:
                return HttpResponse(e.message, status_code=e.httpcode)

            channel.save()
        except requests.exceptions.RequestException:
            return HttpResponseNotFound('channel not found')

    ret_obj = searchqueries.generate_return_object(field_maps, channel, context)

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _channels_get(request):
    # TODO
    return HttpResponse('hello')
