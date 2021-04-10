from django.http import HttpResponse, HttpResponseNotAllowed

from api import query_utils


def explore(request):
    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _explore_get(request, uuid_)


def _explore_get(request, uuid_):
    # TODO for the time being, this will just be static data, because a recommendation engine is quite an endeavour
    ret_obj = [
        {
            'tag': 'American News',
            'feedUuids': [],
        },
        {
            'tag': 'Tech',
            'feedUuids': [],
        },
        {
            'tag': 'Home',
            'feedUuids': [],
        },
        {
            'tag': 'Business',
            'feedUuids': [],
        },
        {
            'tag': 'Marketing',
            'feedUuids': [],
        },
    ]

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)
