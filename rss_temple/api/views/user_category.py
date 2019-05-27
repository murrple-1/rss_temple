import uuid

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db import transaction, IntegrityError
from django.db.models import Q

import ujson

from api import models, query_utils
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


def user_categories_query(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _user_categories_query_post(request)


def user_categories_apply(request):
    permitted_methods = {'PUT'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'PUT':
        return _user_categories_apply_put(request)


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
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    user_category = None
    try:
        user_category = models.UserCategory.objects.get(
            uuid=_uuid_, user=request.user)
    except models.UserCategory.DoesNotExist:
        return HttpResponseNotFound('user category not found')

    ret_obj = query_utils.generate_return_object(
        field_maps, user_category, context)

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _user_category_post(request):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    field_maps = None
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
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

    ret_obj = query_utils.generate_return_object(
        field_maps, user_category, context)

    content, content_type = query_utils.serialize_content(ret_obj)

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


def _user_categories_query_post(request):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

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

    count = None
    try:
        count = query_utils.get_count(_json)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    skip = None
    try:
        skip = query_utils.get_skip(_json)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    sort = None
    try:
        sort = query_utils.get_sort(_json, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    search = None
    try:
        search = [Q(user=request.user)] + \
            query_utils.get_search(context, _json, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    field_maps = None
    try:
        fields = query_utils.get_fields__json(_json)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    return_objects = None
    try:
        return_objects = query_utils.get_return_objects(_json)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    return_total_count = None
    try:
        return_total_count = query_utils.get_return_total_count(_json)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    user_categories = models.UserCategory.objects.filter(*search)

    ret_obj = {}

    if return_objects:
        objs = []
        for user_category in user_categories.order_by(
                *sort)[skip:skip + count]:
            obj = query_utils.generate_return_object(
                field_maps, user_category, context)
            objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = user_categories.count()

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _user_categories_apply_put(request):
    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, dict):
        return HttpResponseBadRequest('JSON body must be object')  # pragma: no cover

    all_feed_uuids = set()
    all_user_category_uuids = set()

    mappings = {}

    for feed_uuid, user_category_uuids in _json.items():
        _feed_uuid = None
        try:
            _feed_uuid = uuid.UUID(feed_uuid)
        except ValueError:
            return HttpResponseBadRequest('JSON body key malformed')

        all_feed_uuids.add(_feed_uuid)

        if not isinstance(user_category_uuids, list):
            return HttpResponseBadRequest('JSON body element must be array')

        try:
            user_category_uuids = frozenset(
                uuid.UUID(s) for s in user_category_uuids)
        except (ValueError, TypeError):
            return HttpResponseBadRequest('JSON body value malformed')

        all_user_category_uuids.update(user_category_uuids)

        mappings[_feed_uuid] = user_category_uuids

    feeds = dict((feed.uuid, feed)
                 for feed in models.Feed.objects.filter(uuid__in=all_feed_uuids))

    if len(feeds) < len(all_feed_uuids):
        return HttpResponseNotFound('feed not found')

    user_categories = dict((user_category.uuid, user_category) for user_category in models.UserCategory.objects.filter(
        uuid__in=all_user_category_uuids, user=request.user))

    if len(user_categories) < len(all_user_category_uuids):
        return HttpResponseNotFound('user category not found')

    feed_user_category_mappings = []

    for feed_uuid, user_category_uuids in mappings.items():
        for user_category_uuid in user_category_uuids:
            feed_user_category_mapping = models.FeedUserCategoryMapping(
                user_category=user_categories[user_category_uuid], feed=feeds[feed_uuid])
            feed_user_category_mappings.append(feed_user_category_mapping)

    with transaction.atomic():
        models.FeedUserCategoryMapping.objects.filter(
            feed__in=feeds.values()).delete()
        models.FeedUserCategoryMapping.objects.bulk_create(
            feed_user_category_mappings)

    return HttpResponse()
