import uuid

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.core.cache import caches

import ujson

from api import models, query_utils
from api.exceptions import QueryException
from api.context import Context


_OBJECT_NAME = 'tag'


def tag(request, uuid_):
    uuid_ = uuid.UUID(uuid_)

    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _tag_get(request, uuid_)


def tags_query(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _tags_query_post(request)


def tags_query_popular(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _tags_query_popular_post(request)


def _tag_get(request, uuid_):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    field_maps = None
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    tag = None
    try:
        tag = models.Tag.objects.get(
            uuid=uuid_)
    except models.Tag.DoesNotExist:
        return HttpResponseNotFound('tag not found')

    ret_obj = query_utils.generate_return_object(
        field_maps, tag, context)

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _tags_query_post(request):
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

    tags = models.Tag.objects.filter(*search)

    ret_obj = {}

    if return_objects:
        objs = []
        for tag in tags.order_by(
                *sort)[skip:skip + count]:
            obj = query_utils.generate_return_object(
                field_maps, tag, context)
            objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = tags.count()

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _tags_query_popular_post(request):
    cache = caches['tags']

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

    search = []

    tags_queryset = None
    popular_uuids = cache.get('popular_uuids')
    if popular_uuids is not None:
        tags_queryset = models.Tag.objects.filter(uuid__in=popular_uuids[skip:skip + count])
    else:
        tags_queryset = models.Tag.objects.order_by('uuid')[skip:skip + count]

    tags = dict((tag.uuid, tag) for tag in tags_queryset)

    if popular_uuids is None:
        popular_uuids = list(tags.keys())

    ret_obj = {}

    if return_objects:
        objs = []
        for tag_uuid in popular_uuids:
            tag = tags[tag_uuid]
            obj = query_utils.generate_return_object(
                field_maps, tag, context)
            objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = len(popular_uuids)

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)
