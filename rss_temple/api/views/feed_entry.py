import uuid

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db.utils import IntegrityError

import ujson

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


def feed_entry_read(request, _uuid):
    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entry_read_post(request, _uuid)
    elif request.method == 'DELETE':
        return _feed_entry_read_delete(request, _uuid)


def feed_entries_read(request):
    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entries_read_post(request)
    elif request.method == 'DELETE':
        return _feed_entries_read_delete(request)


def feed_entry_favorite(request, _uuid):
    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entry_favorite_post(request, _uuid)
    elif request.method == 'DELETE':
        return _feed_entry_favorite_delete(request, _uuid)


def feed_entries_favorite(request):
    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entries_favorite_post(request)
    elif request.method == 'DELETE':
        return _feed_entries_favorite_delete(request)


def _feed_entry_get(request, _uuid):
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

    feed_entry = None
    try:
        feed_entry = models.FeedEntry.objects.get(uuid=_uuid_)
    except models.FeedEnrty.DoesNotExist:
        return HttpResponseNotFound('feed entry not found')

    ret_obj = searchqueries.generate_return_object(
        field_maps, feed_entry, context)

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


def _feed_entry_read_post(request, _uuid):
    _uuid = uuid.UUID(_uuid)

    feed_entry = None
    try:
        feed_entry = models.FeedEntry.objects.get(uuid=_uuid)
    except models.FeedEnrty.DoesNotExist:
        return HttpResponseNotFound('feed entry not found')

    read_feed_entry_user_mapping = models.ReadFeedEntryUserMapping(
        feed_entry=feed_entry, user=request.user)

    try:
        read_feed_entry_user_mapping.save()
    except IntegrityError:
        pass

    return HttpResponse()


def _feed_entry_read_delete(request, _uuid):
    _uuid = uuid.UUID(_uuid)

    models.ReadFeedEntryUserMapping.objects.filter(
        feed_entry_id=_uuid, user=request.user).delete()

    return HttpResponse()


def _feed_entries_read_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, list):
        return HttpResponseBadRequest('JSON body must be array')  # pragma: no cover

    if len(_json) < 1:
        return HttpResponse()

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(_uuid) for _uuid in _json)
    except ValueError:
        return HttpResponseBadRequest('uuid malformed')

    feed_entries = list(models.FeedEntry.objects.filter(uuid__in=_ids))

    if len(feed_entries) != len(_ids):
        return HttpResponseNotFound('feed entry not found')

    for feed_entry in feed_entries:
        read_feed_entry_user_mapping = models.ReadFeedEntryUserMapping(
            feed_entry=feed_entry, user=request.user)

        try:
            read_feed_entry_user_mapping.save()
        except IntegrityError:
            pass

    return HttpResponse()


def _feed_entries_read_delete(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, list):
        return HttpResponseBadRequest('JSON body must be array')  # pragma: no cover

    if len(_json) < 1:
        return HttpResponse()

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(_uuid) for _uuid in _json)
    except ValueError:
        return HttpResponseBadRequest('uuid malformed')

    models.ReadFeedEntryUserMapping.objects.filter(
        feed_entry_id__in=_ids, user=request.user).delete()

    return HttpResponse()


def _feed_entry_favorite_post(request, _uuid):
    _uuid = uuid.UUID(_uuid)

    feed_entry = None
    try:
        feed_entry = models.FeedEntry.objects.get(uuid=_uuid)
    except models.FeedEnrty.DoesNotExist:
        return HttpResponseNotFound('feed entry not found')

    favorite_feed_entry_user_mapping = models.FavoriteFeedEntryUserMapping(
        feed_entry=feed_entry, user=request.user)

    try:
        favorite_feed_entry_user_mapping.save()
    except IntegrityError:
        pass

    return HttpResponse()


def _feed_entry_favorite_delete(request, _uuid):
    _uuid = uuid.UUID(_uuid)

    models.FavoriteFeedEntryUserMapping.objects.filter(
        feed_entry_id=_uuid, user=request.user).delete()

    return HttpResponse()


def _feed_entries_favorite_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, list):
        return HttpResponseBadRequest('JSON body must be array')  # pragma: no cover

    if len(_json) < 1:
        return HttpResponse()

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(_uuid) for _uuid in _json)
    except ValueError:
        return HttpResponseBadRequest('uuid malformed')

    feed_entries = list(models.FeedEntry.objects.filter(uuid__in=_ids))

    if len(feed_entries) != len(_ids):
        return HttpResponseNotFound('feed entry not found')

    for feed_entry in feed_entries:
        favorite_feed_entry_user_mapping = models.FavoriteFeedEntryUserMapping(
            feed_entry=feed_entry, user=request.user)

        try:
            favorite_feed_entry_user_mapping.save()
        except IntegrityError:
            pass

    return HttpResponse()


def _feed_entries_favorite_delete(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    _json = None
    try:
        _json = ujson.loads(
            request.body, request.encoding or settings.DEFAULT_CHARSET)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if not isinstance(_json, list):
        return HttpResponseBadRequest('JSON body must be array')  # pragma: no cover

    if len(_json) < 1:
        return HttpResponse()

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(_uuid) for _uuid in _json)
    except ValueError:
        return HttpResponseBadRequest('uuid malformed')

    models.FavoriteFeedEntryUserMapping.objects.filter(
        feed_entry_id__in=_ids, user=request.user).delete()

    return HttpResponse()
