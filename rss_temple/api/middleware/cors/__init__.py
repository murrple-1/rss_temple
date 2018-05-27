from django.http import HttpResponse
from django.conf import settings

_CORS_ALLOW_ORIGINS = getattr(settings, 'CORS_ALLOW_ORIGINS', '*')
_CORS_ALLOW_METHODS = getattr(
    settings,
    'CORS_ALLOW_METHODS',
    'GET,POST,OPTIONS')
_CORS_ALLOW_HEADERS = getattr(
    settings,
    'CORS_ALLOW_HEADERS',
    'Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization')
_CORS_EXPOSE_HEADERS = getattr(settings, 'CORS_EXPOSE_HEADERS', '')


class CORSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response


    def __call__(self, request):
        response = None
        if request.method == 'OPTIONS':
            response = HttpResponse()
        else:
            response = self.get_response(request)

        cors_enabled = False

        if _CORS_ALLOW_ORIGINS is not None:
            if 'HTTP_ORIGIN' in request.META:
                origin = request.META['HTTP_ORIGIN']

                if isinstance(_CORS_ALLOW_ORIGINS, str):
                    if _CORS_ALLOW_ORIGINS == '*':
                        response['Access-Control-Allow-Origin'] = '*'
                        cors_enabled = True
                    elif origin == _CORS_ALLOW_ORIGINS:
                        response['Access-Control-Allow-Origin'] = origin
                        cors_enabled = True
                elif isinstance(_CORS_ALLOW_ORIGINS, list):
                    if origin in _CORS_ALLOW_ORIGINS:
                        response['Access-Control-Allow-Origin'] = origin
                        cors_enabled = True

        if cors_enabled:
            if _CORS_ALLOW_METHODS is not None:
                response['Access-Control-Allow-Methods'] = _CORS_ALLOW_METHODS

            if _CORS_ALLOW_HEADERS is not None:
                response['Access-Control-Allow-Headers'] = _CORS_ALLOW_HEADERS

            if _CORS_EXPOSE_HEADERS is not None:
                response['Access-Control-Expose-Headers'] = _CORS_EXPOSE_HEADERS

        return response
