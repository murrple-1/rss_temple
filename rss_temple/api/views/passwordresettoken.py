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
    return HttpResponse()


def _passwordresettoken_reset_post(request):
    return HttpResponse()
