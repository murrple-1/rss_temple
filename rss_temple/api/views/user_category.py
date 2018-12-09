import uuid

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db import IntegrityError
from django.db.models import Q

import ujson

from api import models, searchqueries
from api.exceptions import QueryException
from api.context import Context


_OBJECT_NAME = 'usercategory'


def user_category(request, _uuid):
    permitted_methods = {'GET', 'POST', 'PUT', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _user_category_get(request, _uuid)
    elif request.method == 'POST':
        return _user_category_post(request)
    elif request.method == 'PUT':
        return _user_category_put(request, _uuid)
    elif request.method == 'DELETE':
        return _user_category_delete(request, _uuid)


def user_category_feeds(request, _uuid):
    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _user_category_feeds_post(request, _uuid)
    elif request.method == 'DELETE':
        return _user_category_feeds_delete(request, _uuid)


def user_categories(request):
    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _user_categories_get(request)


def _user_category_get(request, _uuid):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    _uuid_ = None
    try:
        _uuid_ = uuid.UUID(_uuid)
    except (ValueError, TypeError):
        return HttpResponseBadRequest('uuid malformed')

    field_maps = None
    try:
        field_maps = searchqueries.get_field_maps(request.GET, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    user_category = None
    try:
        user_category = models.UserCategory.objects.get(
            uuid=_uuid_, user=request.user)
    except models.UserCategory.DoesNotExist:
        return HttpResponseNotFound('user category not found')

    ret_obj = searchqueries.generate_return_object(
        field_maps, user_category, context)

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _user_category_post(request):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    field_maps = None
    try:
        field_maps = searchqueries.get_field_maps(request.GET, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, dict):
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    if 'text' not in _json:
        return HttpResponseBadRequest('\'text\' missing')

    if not isinstance(_json['text'], str):
        return HttpResponseBadRequest('\'text\' must be string')

    user_category = models.UserCategory(user=request.user, text=_json['text'])

    try:
        user_category.save()
    except IntegrityError:
        return HttpResponse('user category already exists', status=409)

    ret_obj = searchqueries.generate_return_object(
        field_maps, user_category, context)

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _user_category_put(request, _uuid):
    _uuid_ = None
    try:
        _uuid_ = uuid.UUID(_uuid)
    except (ValueError, TypeError):
        return HttpResponseBadRequest('uuid malformed')

    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    user_category = None
    try:
        user_category = models.UserCategory.objects.get(
            uuid=_uuid_, user=request.user)
    except models.UserCategory.DoesNotExist:
        return HttpResponseNotFound('user category not found')

    has_changed = False

    if not isinstance(_json, dict):
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    if 'text' in _json:
        if not isinstance(_json['text'], str):
            return HttpResponseBadRequest('\'text\' must be string')

        user_category.text = _json['text']
        has_changed = True

    if has_changed:
        try:
            user_category.save()
        except IntegrityError:
            return HttpResponse('user category already exists', status=409)

    return HttpResponse()


def _user_category_delete(request, _uuid):
    _uuid_ = None
    try:
        _uuid_ = uuid.UUID(_uuid)
    except (ValueError, TypeError):
        return HttpResponseBadRequest('uuid malformed')

    count, _ = models.UserCategory.objects.filter(
        uuid=_uuid_, user=request.user).delete()

    if count < 1:
        return HttpResponseNotFound('user category not found')

    return HttpResponse()


def _user_categories_get(request):
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
        search = [Q(user=request.user)] + \
            searchqueries.get_search(context, query_dict, _OBJECT_NAME)
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

    user_categories = models.UserCategory.objects.filter(*search)

    ret_obj = {}

    if return_objects:
        objs = []
        for user_category in user_categories.order_by(
                *sort)[skip:skip + count]:
            obj = searchqueries.generate_return_object(
                field_maps, user_category, context)
            objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = user_categories.count()

    content, content_type = searchqueries.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _user_category_feeds_post(request, _uuid):
    _uuid = uuid.UUID(_uuid)

    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    user_category = None
    try:
        user_category = models.UserCategory.objects.get(
            uuid=_uuid, user=request.user)
    except models.UserCategory.DoesNotExist:
        return HttpResponseNotFound('user category not found')

    feed_uuids = None
    if isinstance(_json, list):
        try:
            feed_uuids = frozenset(uuid.UUID(s) for s in _json)
        except (ValueError, TypeError):
            return HttpResponseBadRequest('element must be UUID')
    elif isinstance(_json, str):
        try:
            feed_uuids = [uuid.UUID(_json)]
        except ValueError:
            return HttpResponseBadRequest('JSON body must be UUID')
    else:
        return HttpResponseBadRequest('JSON body must be array or UUID')

    feeds = list(models.Feed.objects.filter(uuid__in=feed_uuids))

    if len(feeds) < len(feed_uuids):
        return HttpResponseNotFound('feed not found')

    feed_user_category_mappings = []

    for feed in feeds:
        feed_user_category_mapping = models.FeedUserCategoryMapping(
            user_category=user_category, feed=feed)
        feed_user_category_mappings.append(feed_user_category_mapping)

    try:
        models.FeedUserCategoryMapping.objects.bulk_create(feed_user_category_mappings)
    except IntegrityError:
        return HttpResponse('mapping already exists', status=409)

    return HttpResponse()


def _user_category_feeds_delete(request, _uuid):
    _uuid = uuid.UUID(_uuid)

    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    user_category = None
    try:
        user_category = models.UserCategory.objects.get(
            uuid=_uuid, user=request.user)
    except models.UserCategory.DoesNotExist:
        return HttpResponseNotFound('user category not found')

    feed_uuids = None

    if isinstance(_json, list):
        try:
            feed_uuids = frozenset(uuid.UUID(s) for s in _json)
        except (ValueError, TypeError):
            return HttpResponseBadRequest('element must be UUID')
    elif isinstance(_json, str):
        try:
            feed_uuids = [uuid.UUID(_json)]
        except ValueError:
            return HttpResponseBadRequest('JSON body must be UUID')
    else:
        return HttpResponseBadRequest('JSON body must be array or UUID')

    feed_user_category_mappings = models.FeedUserCategoryMapping.objects.filter(user_category=user_category, feed_id__in=feed_uuids)

    if feed_user_category_mappings.count() < len(feed_uuids):
        return HttpResponseNotFound('mapping not found')

    feed_user_category_mappings.delete()

    return HttpResponse()
