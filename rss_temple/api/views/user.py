import uuid

from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotModified

from ..exceptions import QueryException
from .. import models, searchqueries

_OBJECT_NAME = 'user'

def user(request):
    permitted_methods = ['GET']

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)

    if request.method == 'GET':
        return _user_get(request)

def _user_get(request):
    context = searchqueries.Context()
    context.parse_query_dict(request.GET)

    user = request.user

    field_maps = None
    try:
        field_maps = searchqueries.get_field_maps(request.GET, _OBJECT_NAME)
    except QueryException as e:
        return HttpResponse(e.message, status_code=e.httpcode)

    ret_obj = searchqueries.generate_return_object(field_maps, user, context)

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)
