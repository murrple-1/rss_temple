from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed

import ujson

from api import models


def passwordresettoken_request(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _passwordresettoken_request_post(request)


def passwordresettoken_reset(request):
    permitted_methods = {'POST'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'POST':
        return _passwordresettoken_reset_post(request)


def _passwordresettoken_request_post(request):
    email = request.GET.get('email')

    if email is None:
        return HttpResponseBadRequest('\'email\' missing')

    return HttpResponse()


def _passwordresettoken_reset_post(request):
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

    return HttpResponse()
