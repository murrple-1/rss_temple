import uuid

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db.utils import IntegrityError

import ujson

from api import models, query_utils
from api.exceptions import QueryException
from api.context import Context


_OBJECT_NAME = 'feedentry'


def feed_entry(request, uuid_):
    uuid_ = uuid.UUID(uuid_)

    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _feed_entry_get(request, uuid_)


def feed_entries_query(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entries_query_post(request)


def feed_entry_read(request, uuid_):
    uuid_ = uuid.UUID(uuid_)

    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entry_read_post(request, uuid_)
    elif request.method == 'DELETE':
        return _feed_entry_read_delete(request, uuid_)


def feed_entries_read(request):
    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entries_read_post(request)
    elif request.method == 'DELETE':
        return _feed_entries_read_delete(request)


def feed_entry_favorite(request, uuid_):
    uuid_ = uuid.UUID(uuid_)

    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entry_favorite_post(request, uuid_)
    elif request.method == 'DELETE':
        return _feed_entry_favorite_delete(request, uuid_)


def feed_entries_favorite(request):
    permitted_methods = {'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entries_favorite_post(request)
    elif request.method == 'DELETE':
        return _feed_entries_favorite_delete(request)


def _feed_entry_get(request, uuid_):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    field_maps = None
    try:
        fields = query_utils.get_fields__query_dict(request.GET)
        field_maps = query_utils.get_field_maps(fields, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    feed_entry = None
    try:
        feed_entry = models.FeedEntry.objects.get(uuid=uuid_)
    except models.FeedEntry.DoesNotExist:
        return HttpResponseNotFound('feed entry not found')

    ret_obj = query_utils.generate_return_object(
        field_maps, feed_entry, context)

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _feed_entries_query_post(request):
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

    feed_entries = models.FeedEntry.objects.filter(*search)

    ret_obj = {}

    if return_objects:
        objs = []
        for feed_entry in feed_entries.order_by(
                *sort)[skip:skip + count]:
            obj = query_utils.generate_return_object(
                field_maps, feed_entry, context)
            objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = feed_entries.count()

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _feed_entry_read_post(request, uuid_):
    feed_entry = None
    try:
        feed_entry = models.FeedEntry.objects.get(uuid=uuid_)
    except models.FeedEntry.DoesNotExist:
        return HttpResponseNotFound('feed entry not found')

    read_feed_entry_user_mapping = models.ReadFeedEntryUserMapping(
        feed_entry=feed_entry, user=request.user)

    try:
        read_feed_entry_user_mapping.save()
    except IntegrityError:
        pass

    return HttpResponse()


def _feed_entry_read_delete(request, uuid_):
    models.ReadFeedEntryUserMapping.objects.filter(
        feed_entry_id=uuid_, user=request.user).delete()

    return HttpResponse()


def _feed_entries_read_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not list:
        return HttpResponseBadRequest('JSON body must be array')  # pragma: no cover

    if len(json_) < 1:
        return HttpResponse()

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in json_)
    except (ValueError, TypeError, AttributeError):
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

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not list:
        return HttpResponseBadRequest('JSON body must be array')  # pragma: no cover

    if len(json_) < 1:
        return HttpResponse()

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in json_)
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest('uuid malformed')

    models.ReadFeedEntryUserMapping.objects.filter(
        feed_entry_id__in=_ids, user=request.user).delete()

    return HttpResponse()


def _feed_entry_favorite_post(request, uuid_):
    feed_entry = None
    try:
        feed_entry = models.FeedEntry.objects.get(uuid=uuid_)
    except models.FeedEntry.DoesNotExist:
        return HttpResponseNotFound('feed entry not found')

    favorite_feed_entry_user_mapping = models.FavoriteFeedEntryUserMapping(
        feed_entry=feed_entry, user=request.user)

    try:
        favorite_feed_entry_user_mapping.save()
    except IntegrityError:
        pass

    return HttpResponse()


def _feed_entry_favorite_delete(request, uuid_):
    models.FavoriteFeedEntryUserMapping.objects.filter(
        feed_entry_id=uuid_, user=request.user).delete()

    return HttpResponse()


def _feed_entries_favorite_post(request):
    if not request.body:
        return HttpResponseBadRequest('no HTTP body')  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not list:
        return HttpResponseBadRequest('JSON body must be array')  # pragma: no cover

    if len(json_) < 1:
        return HttpResponse()

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in json_)
    except (ValueError, TypeError, AttributeError):
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

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest('HTTP body cannot be parsed')

    if type(json_) is not list:
        return HttpResponseBadRequest('JSON body must be array')  # pragma: no cover

    if len(json_) < 1:
        return HttpResponse()

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in json_)
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest('uuid malformed')

    models.FavoriteFeedEntryUserMapping.objects.filter(
        feed_entry_id__in=_ids, user=request.user).delete()

    return HttpResponse()
