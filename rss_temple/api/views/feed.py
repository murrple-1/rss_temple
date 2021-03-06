from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db import transaction

import requests

import ujson

from url_normalize import url_normalize

from api import models, query_utils, feed_handler, rss_requests
from api.exceptions import QueryException
from api.context import Context


_OBJECT_NAME = 'feed'


def feed(request):
    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _feed_get(request)


def feeds_query(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feeds_query_post(request)


def feed_subscribe(request):
    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_subscribe_post(request)
    elif request.method == 'DELETE':
        return _feed_subscribe_delete(request)


def _save_feed(url):
    response = None
    try:
        response = rss_requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        raise QueryException('feed not found', 404)

    with transaction.atomic():
        d = feed_handler.text_2_d(response.text)
        feed = feed_handler.d_feed_2_feed(d.feed, url)
        feed.with_subscription_data()
        feed.save()

        feed_entries = []
        for d_entry in d.get('entries', []):
            feed_entry = feed_handler.d_entry_2_feed_entry(d_entry)
            feed_entry.feed = feed
            feed_entries.append(feed_entry)

        models.FeedEntry.objects.bulk_create(feed_entries)

        return feed


def _feed_get(request):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    url = request.GET.get('url')
    if not url:
        return HttpResponseBadRequest('\'url\' missing')

    url = url_normalize(url)

    field_maps = None
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    feed = None
    try:
        feed = models.Feed.objects.with_subscription_data(
            request.user).get(feed_url=url)
    except models.Feed.DoesNotExist:
        try:
            feed = _save_feed(url)
        except QueryException as e:
            return HttpResponse(e.message, status=e.httpcode)

    ret_obj = query_utils.generate_return_object(field_maps, feed, context)

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _feeds_query_post(request):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not dict:
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    count = None
    try:
        count = query_utils.get_count(json_)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    skip = None
    try:
        skip = query_utils.get_skip(json_)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    sort = None
    try:
        sort = query_utils.get_sort(json_, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    search = None
    try:
        search = query_utils.get_search(context, json_, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    field_maps = None
    try:
        fields = query_utils.get_fields__json(json_)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    return_objects = None
    try:
        return_objects = query_utils.get_return_objects(json_)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    return_total_count = None
    try:
        return_total_count = query_utils.get_return_total_count(json_)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    feeds = models.Feed.objects.with_subscription_data(
        request.user).filter(*search)

    ret_obj = {}

    if return_objects:
        objs = []
        for feed in feeds.order_by(
                *sort)[skip:skip + count]:
            obj = query_utils.generate_return_object(
                field_maps, feed, context)
            objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = feeds.count()

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _feed_subscribe_post(request):
    user = request.user

    url = request.GET.get('url')
    if not url:
        return HttpResponseBadRequest('\'url\' missing')

    url = url_normalize(url)

    feed = None
    try:
        feed = models.Feed.objects.get(feed_url=url)
    except models.Feed.DoesNotExist:
        try:
            feed = _save_feed(url)
        except QueryException as e:
            return HttpResponse(e.message, status=e.httpcode)

    custom_title = request.GET.get('customtitle')

    existing_subscription_list = list(models.SubscribedFeedUserMapping.objects.filter(
        user=user).values_list('feed__feed_url', 'custom_feed_title'))

    existing_feed_urls = frozenset(t[0] for t in existing_subscription_list)
    existing_custom_titles = frozenset(
        t[1] for t in existing_subscription_list if t[1] is not None)

    if custom_title is not None and custom_title in existing_custom_titles:
        return HttpResponse('custom title already used', status=409)

    if feed.feed_url in existing_feed_urls:
        return HttpResponse('user already subscribed', status=409)

    models.SubscribedFeedUserMapping.objects.create(
        user=user, feed=feed, custom_feed_title=custom_title)

    return HttpResponse()


def _feed_subscribe_delete(request):
    url = request.GET.get('url')
    if not url:
        return HttpResponseBadRequest('\'url\' missing')

    url = url_normalize(url)

    count, _ = models.SubscribedFeedUserMapping.objects.filter(
        user=request.user, feed__feed_url=url).delete()

    if count < 1:
        return HttpResponseNotFound('user not subscribed')

    return HttpResponse()
