import importlib

from django.test import TestCase
from django.http.request import HttpRequest
from django.http.response import HttpResponse

import api.middleware.profiling as profiling


class ProfilingTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        # reload without messing up the settings
        importlib.reload(profiling)

    def test_middleware(self):
        with self.settings(PROFILING_OUTPUT_FILE='api/tests/test_files/profiling/profile', DEBUG=True):
            importlib.reload(profiling)
            middleware = profiling.ProfileMiddleware(
                lambda request: HttpResponse())

            request = HttpRequest()

            response = middleware(request)
            assert response  # PyFlakes

            request = HttpRequest()
            request.GET['_profile'] = 'true'

            response = middleware(request)
            assert response  # PyFlakes

        with self.settings(PROFILING_OUTPUT_FILE=None, DEBUG=False):
            importlib.reload(profiling)
            middleware = profiling.ProfileMiddleware(
                lambda request: HttpResponse())

            request = HttpRequest()

            response = middleware(request)
            assert response  # PyFlakes
