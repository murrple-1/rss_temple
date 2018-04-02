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


def channel_subscribe(request):
    permitted_methods = ['POST', 'DELETE']

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)

    if request.method == 'POST':
        return _channel_subscribe_post(request)
    elif request.method == 'DELETE':
        return _channel_subscribe_delete(request)


def __link_to_channel(link, save=True):
    channel = None
    try:
        channel = models.Channel.objects.get(feed_link=link)
    except models.Channel.DoesNotExist:
        response = None
        try:
            response = requests.get(link, headers={
                'User-Agent': 'RSS Temple',
            })
        except requests.exceptions.RequestException:
            raise QueryException('channel not found', 404)

        d = feedparser.parse(response.text)

        logger().info('channel info: %s', pprint.pformat(d))

        channel = models.Channel()

        try:
            channel.title = d['channel']['title']
            channel.description = d['channel']['description']
            channel.home_link = d['channel']['link']
            channel.feed_link = link
        except KeyError:
            raise QueryException('feed malformed', 401)

        if save:
            channel.save()

    return channel


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
        channel = __link_to_channel(link)
    except QueryException as e:
        return HttpResponse(e.message, status_code=e.httpcode)

    ret_obj = searchqueries.generate_return_object(field_maps, channel, context)

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _channels_get(request):
    # TODO
    return HttpResponse()


def _channel_subscribe_post(request):
    user = request.user

    link = request.GET.get('link')
    if not link:
        return HttpResponseBadRequest('\'link\' missing')

    if not request.body:
        return HttpResponseBadRequest('no HTTP body')

    _json = None
    try:
        _json = ujson.loads(request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, dict):
        return HttpResponseBadRequest('JSON body must be object')

    channel = None
    try:
        channel = __link_to_channel(link)
    except QueryException as e:
        return HttpResponse(e.message, status_code=e.httpcode)

    if models.UserChannelMapping.objects.filter(user=user, channel=channel).exists():
        return HttpResponse('user already subscribed', status_code=409)

    user_channel_mapping = models.UserChannelMapping()
    user_channel_mapping.user = user
    user_channel_mapping.channel = channel

    user_channel_mapping.save()

    return HttpResponse()
