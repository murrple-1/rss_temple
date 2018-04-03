import pprint
import logging

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed

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
        return HttpResponse(e.message, status=e.httpcode)

    channel = None
    try:
        channel = __link_to_channel(link)
    except QueryException as e:
        return HttpResponse(e.message, status=e.httpcode)

    ret_obj = searchqueries.generate_return_object(field_maps, channel, context)

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _channels_get(request):
    query_dict = request.GET
    context = searchqueries.Context()
    context.parse_query_dict(query_dict)

    count = None
    try:
        count = searchqueries.get_count(query_dict)
    except QueryException as e:
        return HttpResponse(e.message, status=e.httpCode)

    skip = None
    try:
        skip = searchqueries.get_skip(query_dict)
    except QueryException as e:
        return HttpResponse(e.message, status=e.httpCode)

    sort = None
    try:
        sort = searchqueries.get_sort(query_dict, _OBJECT_NAME)
    except QueryException as e:
        return HttpResponse(e.message, status=e.httpCode)

    search = None
    try:
        search = searchqueries.get_search(query_dict, _OBJECT_NAME)
    except QueryException as e:
        return HttpResponse(e.message, status=e.httpCode)

    field_maps = None
    try:
        field_maps = searchqueries.get_field_maps(query_dict, _OBJECT_NAME)
    except QueryException as e:
        return HttpResponse(e.message, status=e.httpCode)

    return_objects = None
    try:
        return_objects = searchqueries.get_return_objects(query_dict)
    except QueryException as e:
        return HttpResponse(e.message, status=e.httpCode)

    return_total_count = None
    try:
        return_total_count = searchqueries.get_return_total_count(query_dict)
    except QueryException as e:
        return HttpResponse(e.message, status=e.httpCode)

    channels = models.Channel.objects.filter(*search)

    ret_obj = {}

    if return_objects:
        objs = []
        for channel in channels.order_by(
                *sort)[skip:skip + count]:
            obj = searchqueries.generate_return_object(
                field_maps, channel, context)
            objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = channels.count()

    content, content_type = searchqueries.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _channel_subscribe_post(request):
    user = request.user

    link = request.GET.get('link')
    if not link:
        return HttpResponseBadRequest('\'link\' missing')

    channel = None
    try:
        channel = __link_to_channel(link)
    except QueryException as e:
        return HttpResponse(e.message, status=e.httpcode)

    if models.ChannelUserMapping.objects.filter(user=user, channel=channel).exists():
        return HttpResponse('user already subscribed', status=409)

    channel_user_mapping = models.ChannelUserMapping()
    channel_user_mapping.user = user
    channel_user_mapping.channel = channel

    channel_user_mapping.save()

    return HttpResponse()
