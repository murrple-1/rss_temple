import itertools
import re
import uuid

import ujson
from django.core.cache import caches
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)

from api import models, query_utils
from api.exceptions import QueryException

_OBJECT_NAME = "feedentry"


def feed_entry(request, uuid_):
    uuid_ = uuid.UUID(uuid_)

    permitted_methods = {"GET"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "GET":
        return _feed_entry_get(request, uuid_)


def feed_entries_query(request):
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _feed_entries_query_post(request)


def feed_entries_query_stable_create(request):
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _feed_entries_query_stable_create_post(request)


def feed_entries_query_stable(request):
    permitted_methods = {"POST"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _feed_entries_query_stable_post(request)


def feed_entry_read(request, uuid_):
    uuid_ = uuid.UUID(uuid_)

    permitted_methods = {"POST", "DELETE"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _feed_entry_read_post(request, uuid_)
    elif request.method == "DELETE":
        return _feed_entry_read_delete(request, uuid_)


def feed_entries_read(request):
    permitted_methods = {"POST", "DELETE"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _feed_entries_read_post(request)
    elif request.method == "DELETE":
        return _feed_entries_read_delete(request)


def feed_entry_favorite(request, uuid_):
    uuid_ = uuid.UUID(uuid_)

    permitted_methods = {"POST", "DELETE"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _feed_entry_favorite_post(request, uuid_)
    elif request.method == "DELETE":
        return _feed_entry_favorite_delete(request, uuid_)


def feed_entries_favorite(request):
    permitted_methods = {"POST", "DELETE"}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == "POST":
        return _feed_entries_favorite_post(request)
    elif request.method == "DELETE":
        return _feed_entries_favorite_delete(request)


def _feed_entry_get(request, uuid_):
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
        return HttpResponseNotFound("feed entry not found")

    ret_obj = query_utils.generate_return_object(field_maps, feed_entry, request)

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)


def _feed_entries_query_post(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

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
        search = query_utils.get_search(request, json_, _OBJECT_NAME)
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

    feed_entries = models.FeedEntry.annotate_search_vectors(
        models.FeedEntry.objects.all()
    ).filter(*search)

    ret_obj = {}

    if return_objects:
        objs = []
        for feed_entry in feed_entries.order_by(*sort)[skip : skip + count]:
            obj = query_utils.generate_return_object(field_maps, feed_entry, request)
            objs.append(obj)

        ret_obj["objects"] = objs

    if return_total_count:
        ret_obj["totalCount"] = feed_entries.count()

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _feed_entries_query_stable_create_post(request):
    cache = caches["stable_query"]

    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    sort = None
    try:
        sort = query_utils.get_sort(json_, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    search = None
    try:
        search = query_utils.get_search(request, json_, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    token = f"feedentry-{uuid.uuid4().int}"

    cache.set(
        token,
        list(
            models.FeedEntry.annotate_search_vectors(models.FeedEntry.objects.all())
            .filter(*search)
            .order_by(*sort)
            .values_list("uuid", flat=True)
        ),
    )

    content, content_type = query_utils.serialize_content(token)
    return HttpResponse(content, content_type)


def _feed_entries_query_stable_post(request):
    cache = caches["stable_query"]

    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be object")  # pragma: no cover

    token = None
    try:
        token = json_["token"]
    except KeyError:
        return HttpResponseBadRequest("'token' missing")

    if type(token) is not str:
        return HttpResponseBadRequest("'token' must be string")

    if re.search(r"^feedentry-\d+$", token) is None:
        return HttpResponseBadRequest("'token' malformed")

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

    cache.touch(token)
    uuids = cache.get(token, [])

    ret_obj = {}

    if return_objects:
        current_uuids = uuids[skip : skip + count]

        feed_entries = {
            feed_entry.uuid: feed_entry
            for feed_entry in models.FeedEntry.objects.filter(uuid__in=current_uuids)
        }

        objs = []
        if len(current_uuids) == len(feed_entries):
            for uuid_ in current_uuids:
                feed_entry = feed_entries[uuid_]
                obj = query_utils.generate_return_object(
                    field_maps, feed_entry, request
                )
                objs.append(obj)

        ret_obj["objects"] = objs

    if return_total_count:
        ret_obj["totalCount"] = len(uuids)

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _feed_entry_read_post(request, uuid_):
    read_feed_entry_user_mapping = None

    with transaction.atomic():
        feed_entry = None
        try:
            feed_entry = models.FeedEntry.objects.get(uuid=uuid_)
        except models.FeedEntry.DoesNotExist:
            return HttpResponseNotFound("feed entry not found")

        try:
            read_feed_entry_user_mapping = models.ReadFeedEntryUserMapping.objects.get(
                feed_entry=feed_entry, user=request.user
            )
        except models.ReadFeedEntryUserMapping.DoesNotExist:
            read_feed_entry_user_mapping = (
                models.ReadFeedEntryUserMapping.objects.create(
                    feed_entry=feed_entry, user=request.user
                )
            )

    ret_obj = read_feed_entry_user_mapping.read_at.isoformat()

    content, content_type = query_utils.serialize_content(ret_obj)
    return HttpResponse(content, content_type)


def _feed_entry_read_delete(request, uuid_):
    models.ReadFeedEntryUserMapping.objects.filter(
        feed_entry_id=uuid_, user=request.user
    ).delete()

    return HttpResponse(status=204)


def _feed_entries_read_post(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not dict:
        return HttpResponseBadRequest("JSON body must be array")  # pragma: no cover

    q = None

    if "feedUuids" in json_:
        if type(json_["feedUuids"]) is not list:
            return HttpResponseBadRequest("'feedUuids' must be array")

        feed_uuids = set()
        for feed_uuid_str in json_["feedUuids"]:
            if type(feed_uuid_str) is not str:
                return HttpResponseBadRequest("'feedUuids' element must be string")

            try:
                feed_uuids.add(uuid.UUID(feed_uuid_str))
            except ValueError:
                return HttpResponseBadRequest("'feedUuids' element malformed")

        if q is None:
            q = Q(feed__uuid__in=feed_uuids)
        else:
            q |= Q(feed__uuid__in=feed_uuids)  # pragma: no cover

    if "feedEntryUuids" in json_:
        if type(json_["feedEntryUuids"]) is not list:
            return HttpResponseBadRequest("'feedEntryUuids' must be array")

        feed_entry_uuids = set()
        for feed_entry_uuid_str in json_["feedEntryUuids"]:
            if type(feed_entry_uuid_str) is not str:
                return HttpResponseBadRequest("'feedEntryUuids' element must be string")

            try:
                feed_entry_uuids.add(uuid.UUID(feed_entry_uuid_str))
            except ValueError:
                return HttpResponseBadRequest("'feedEntryUuids' element malformed")

        if q is None:
            q = Q(uuid__in=feed_entry_uuids)
        else:
            q |= Q(uuid__in=feed_entry_uuids)

    if q is None:
        return HttpResponseBadRequest("no entries to mark read")

    batch_size = 768
    objs = (
        models.ReadFeedEntryUserMapping(feed_entry=feed_entry, user=request.user)
        for feed_entry in models.FeedEntry.objects.filter(q).iterator()
    )
    with transaction.atomic():
        while True:
            batch = list(itertools.islice(objs, batch_size))
            if not batch:
                break
            models.ReadFeedEntryUserMapping.objects.bulk_create(
                batch, ignore_conflicts=True
            )

    return HttpResponse(status=204)


def _feed_entries_read_delete(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not list:
        return HttpResponseBadRequest("JSON body must be array")  # pragma: no cover

    if len(json_) < 1:
        return HttpResponse(status=204)

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in json_)
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest("uuid malformed")

    models.ReadFeedEntryUserMapping.objects.filter(
        feed_entry_id__in=_ids, user=request.user
    ).delete()

    return HttpResponse(status=204)


def _feed_entry_favorite_post(request, uuid_):
    feed_entry = None
    try:
        feed_entry = models.FeedEntry.objects.get(uuid=uuid_)
    except models.FeedEntry.DoesNotExist:
        return HttpResponseNotFound("feed entry not found")

    favorite_feed_entry_user_mapping = models.FavoriteFeedEntryUserMapping(
        feed_entry=feed_entry, user=request.user
    )

    try:
        favorite_feed_entry_user_mapping.save()
    except IntegrityError:
        pass

    return HttpResponse(status=204)


def _feed_entry_favorite_delete(request, uuid_):
    models.FavoriteFeedEntryUserMapping.objects.filter(
        feed_entry_id=uuid_, user=request.user
    ).delete()

    return HttpResponse(status=204)


def _feed_entries_favorite_post(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not list:
        return HttpResponseBadRequest("JSON body must be array")  # pragma: no cover

    if len(json_) < 1:
        return HttpResponse(status=204)

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in json_)
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest("uuid malformed")

    feed_entries = list(models.FeedEntry.objects.filter(uuid__in=_ids))

    if len(feed_entries) != len(_ids):
        return HttpResponseNotFound("feed entry not found")

    for feed_entry in feed_entries:
        favorite_feed_entry_user_mapping = models.FavoriteFeedEntryUserMapping(
            feed_entry=feed_entry, user=request.user
        )

        try:
            favorite_feed_entry_user_mapping.save()
        except IntegrityError:
            pass

    return HttpResponse(status=204)


def _feed_entries_favorite_delete(request):
    if not request.body:
        return HttpResponseBadRequest("no HTTP body")  # pragma: no cover

    json_ = None
    try:
        json_ = ujson.loads(request.body)
    except ValueError:  # pragma: no cover
        return HttpResponseBadRequest("HTTP body cannot be parsed")

    if type(json_) is not list:
        return HttpResponseBadRequest("JSON body must be array")  # pragma: no cover

    if len(json_) < 1:
        return HttpResponse(status=204)

    _ids = None
    try:
        _ids = frozenset(uuid.UUID(uuid_) for uuid_ in json_)
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest("uuid malformed")

    models.FavoriteFeedEntryUserMapping.objects.filter(
        feed_entry_id__in=_ids, user=request.user
    ).delete()

    return HttpResponse(status=204)
