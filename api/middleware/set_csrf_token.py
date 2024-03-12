from typing import Callable

from django.http import HttpRequest, HttpResponse


class SetCSRFTokenMiddleware:  # pragma: no cover
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        response = self.get_response(request)

        csrf_token = request.META.get("CSRF_TOKEN")
        if csrf_token:
            response["X-CSRFToken"] = csrf_token

        return response
