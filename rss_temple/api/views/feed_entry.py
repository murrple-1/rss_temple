import uuid
import re

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed
from django.db.utils import IntegrityError
from django.db import transaction
from django.core.cache import caches

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


def feed_entries_query_stable_create(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entries_query_stable_create_post(request)


def feed_entries_query_stable(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _feed_entries_query_stable_post(request)


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


def _feed_entries_query_stable_create_post(request):
    cache = caches['stable_query']

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

    token = f'feedentry-{uuid.uuid4().int}'

    cache.set(token, list(models.FeedEntry.objects.filter(
        *search).order_by(*sort).values_list('uuid', flat=True)))

    content, content_type = query_utils.serialize_content(token)
    return HttpResponse(content, content_type)


def _feed_entries_query_stable_post(request):
    cache = caches['stable_query']

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

    token = None
    try:
        token = json_['token']
    except KeyError:
        return HttpResponseBadRequest('\'token\' missing')

    if type(token) is not str:
        return HttpResponseBadRequest('\'token\' must be string')

    if re.search(r'^feedentry-\d+$', token) is None:
        return HttpResponseBadRequest('\'token\' malformed')

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

    uuids = cache.get(token, [])

    ret_obj = {}

    if return_objects:
        current_uuids = uuids[skip:skip + count]

        feed_entries = dict((feed_entry.uuid, feed_entry)
                            for feed_entry in models.FeedEntry.objects.filter(uuid__in=current_uuids))

        objs = []
        if len(current_uuids) == len(feed_entries):
            for uuid_ in current_uuids:
                feed_entry = feed_entries[uuid_]
                obj = query_utils.generate_return_object(
                    field_maps, feed_entry, context)
                objs.append(obj)

        ret_obj['objects'] = objs

    if return_total_count:
        ret_obj['totalCount'] = len(uuids)

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _feed_entry_read_post(request, uuid_):
    context = Context()
    context.parse_request(request)
    context.parse_query_dict(request.GET)

    read_feed_entry_user_mapping = None

    with transaction.atomic():
        feed_entry = None
        try:
            feed_entry = models.FeedEntry.objects.get(uuid=uuid_)
        except models.FeedEntry.DoesNotExist:
            return HttpResponseNotFound('feed entry not found')

        try:
            read_feed_entry_user_mapping = models.ReadFeedEntryUserMapping.objects.get(
                feed_entry=feed_entry, user=request.user)
        except models.ReadFeedEntryUserMapping.DoesNotExist:
            read_feed_entry_user_mapping = models.ReadFeedEntryUserMapping.objects.create(
                feed_entry=feed_entry, user=request.user)

    ret_obj = context.format_datetime(read_feed_entry_user_mapping.read_at)

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _feed_entry_read_delete(request, uuid_):
    models.ReadFeedEntryUserMapping.objects.filter(
        feed_entry_id=uuid_, user=request.user).delete()

    return HttpResponse()


def _feed_entries_read_post(request):
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

    if type(json_) is not list:
        return HttpResponseBadRequest('JSON body must be array')  # pragma: no cover

    if len(json_) < 1:
        return HttpResponse()

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in json_)
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest('uuid malformed')

    read_feed_entry_user_mappings = []
    with transaction.atomic():
        feed_entries = list(models.FeedEntry.objects.filter(uuid__in=_ids))

        if len(feed_entries) != len(_ids):
            return HttpResponseNotFound('feed entry not found')

        old_read_feed_entry_user_mappings = models.ReadFeedEntryUserMapping.objects.filter(
            user=request.user, feed_entry_id__in=_ids)

        for feed_entry in feed_entries:
            read_feed_entry_user_mapping = next(
                (rfem for rfem in old_read_feed_entry_user_mappings if rfem.feed_entry_id == feed_entry.uuid), None)
            if read_feed_entry_user_mapping is None:
                read_feed_entry_user_mapping = models.ReadFeedEntryUserMapping.objects.create(
                    feed_entry=feed_entry, user=request.user)

            read_feed_entry_user_mappings.append(read_feed_entry_user_mapping)

    ret_obj = []
    for read_feed_entry_user_mapping in read_feed_entry_user_mappings:
        ret_obj.append({
            'uuid': str(read_feed_entry_user_mapping.uuid),
            'readAt': context.format_datetime(read_feed_entry_user_mapping.read_at),
        })

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


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
