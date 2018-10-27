from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotAllowed

from api import models


_OBJECT_NAME = 'user_category'


def user_category(request, _uuid):
    permitted_methods = {'GET', 'POST', 'DELETE'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _user_category_get(request)
    elif request.method == 'POST':
        return _user_category_post(request)
    elif request.method == 'DELETE':
        return _user_category_delete(request)


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
    except ValueError:
        return HttpResponseBadRequest('uuid malformed')

    field_maps = None
    try:
        field_maps = searchqueries.get_field_maps(request.GET, _OBJECT_NAME)
    except QueryException as e:  # pragma: no cover
        return HttpResponse(e.message, status=e.httpcode)

    user_category = None
    try:
        user_category = models.UserCategory.objects.get(uuid=_uuid_)
    except models.UserCategory.DoesNotExist:
        return HttpResponseNotFound('user category not found')

    ret_obj = searchqueries.generate_return_object(field_maps, user_category, context)

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)

# TODO