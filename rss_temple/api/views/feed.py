from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db.utils import IntegrityError

from api import models, searchqueries
from api.exceptions import QueryException
import api.feed_handler as feed_handler
from api.context import Context


_OBJECT_NAME = 'feed'


def feed(request):
    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _feed_get(request)


def feeds(request):
    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _feeds_get(request)


def feed_subscribe(request):
    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_subscribe_post(request)
    elif request.method == 'DELETE':
        return _feed_subscribe_delete(request)


def _feed_get(request):
    context = Context()
    context.parse_query_dict(request.GET)

    url = request.GET.get('url')
    if not url:
        return HttpResponseBadRequest('\'url\' missing')

    field_maps = None
    try:
        field_maps = searchqueries.get_field_maps(request.GET, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    feed = None
    try:
        feed = models.Feed.objects.get(feed_url=url)
    except models.Feed.DoesNotExist:
        try:
            d = feed_handler.url_2_d(url)
            feed = feed_handler.d_feed_2_feed(d.feed, url)
            feed.save()
        except QueryException as e:
            return HttpResponse(e.message, status=e.httpcode)

    ret_obj = searchqueries.generate_return_object(field_maps, feed, context)

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _feeds_get(request):
    query_dict = request.GET

    context = Context()
    context.parse_query_dict(query_dict)

    count = None
    try:
        count = searchqueries.get_count(query_dict)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    skip = None
    try:
        skip = searchqueries.get_skip(query_dict)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    sort = None
    try:
        sort = searchqueries.get_sort(query_dict, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    search = None
    try:
        search = searchqueries.get_search(context, query_dict, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    field_maps = None
    try:
        field_maps = searchqueries.get_field_maps(query_dict, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    return_objects = None
    try:
        return_objects = searchqueries.get_return_objects(query_dict)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    return_total_count = None
    try:
        return_total_count = searchqueries.get_return_total_count(query_dict)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    feeds = models.Feed.objects.filter(*search)

    ret_obj = {}

    if return_objects:
        objs = []
        for feed in feeds.order_by(
                *sort)[skip:skip + count]:
            obj = searchqueries.generate_return_object(
                field_maps, feed, context)
            objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = feeds.count()

    content, content_type = searchqueries.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _feed_subscribe_post(request):
    user = request.user

    url = request.GET.get('url')
    if not url:
        return HttpResponseBadRequest('\'url\' missing')

    feed = None
    try:
        feed = models.Feed.objects.get(feed_url=url)
    except models.Feed.DoesNotExist:
        try:
            d = feed_handler.url_2_d(url)
            feed = feed_handler.d_feed_2_feed(d.feed, url)
            feed.save()
        except QueryException as e:
            return HttpResponse(e.message, status=e.httpcode)

    subscribed_feed_user_mapping = models.SubscribedFeedUserMapping(
        user=user, feed=feed)

    try:
        subscribed_feed_user_mapping.save()
    except IntegrityError:
        return HttpResponse('user already subscribed', status=409)

    return HttpResponse()


def _feed_subscribe_delete(request):
    url = request.GET.get('url')
    if not url:
        return HttpResponseBadRequest('\'url\' missing')

    count, _ = models.SubscribedFeedUserMapping.objects.filter(
        user=request.user, feed__feed_url=url).delete()

    if count < 1:
        return HttpResponseNotFound('user not subscribed')

    return HttpResponse()
