import os

from django.conf import settings

_OUTPUT_FILE = settings.PROFILING_OUTPUT_FILE
if _OUTPUT_FILE is not None and settings.DEBUG:
    import cProfile

    _OUTPUT_FILE_DIR = os.path.dirname(_OUTPUT_FILE)
    if not os.path.isdir(_OUTPUT_FILE_DIR):
        os.makedirs(_OUTPUT_FILE_DIR, 0o755)

    class ProfileMiddleware(object):
        def __init__(self, get_response):
            self.get_response = get_response


        def __call__(self, request):
            if request.GET.get('_profile', None) == 'true':
                profile = cProfile.Profile()
                profile.enable()

                response = self.get_response(request)

                profile.disable()

                profile.dump_stats(_OUTPUT_FILE)

                return response
            else:
                return self.get_response(request)
else:
    class ProfileMiddleware(object):
        def __init__(self, get_response):
            self.get_response = get_response


        def __call__(self, request):
            return self.get_response(request)
