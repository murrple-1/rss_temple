import uuid

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed

from api import models, searchqueries
from api.exceptions import QueryException
from api.context import Context


_OBJECT_NAME = 'feedentry'


def feed_entry(request, _uuid):
    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _feed_entry_get(request, _uuid)


def feed_entries(request):
    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _feed_entries_get(request)


def _feed_entry_get(request, _uuid):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    _uuid_ = None
    try:
        _uuid_ = uuid.UUID(_uuid)
    except ValueError:
        return HttpResponseBadRequest('uuid malformed')

    field_maps = None
    try:
        field_maps = searchqueries.get_field_maps(request.GET, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    feed_entry = None
    try:
        feed_entry = models.FeedEntry.objects.get(uuid=_uuid_)
    except models.FeedEnrty.DoesNotExist:
        return HttpResponseNotFound('feed entry not found')

    ret_obj = searchqueries.generate_return_object(field_maps, feed_entry, context)

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _feed_entries_get(request):
    query_dict = request.GET

    context = Context()
    context.parse_request(request)
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

    feed_entries = models.FeedEntry.objects.filter(*search)

    ret_obj = {}

    if return_objects:
        objs = []
        for feed_entry in feed_entries.order_by(
                *sort)[skip:skip + count]:
            obj = searchqueries.generate_return_object(
                field_maps, feed_entry, context)
            objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = feed_entries.count()

    content, content_type = searchqueries.serialize_content(ret_obj)
    return HttpResponse(content, content_type)
