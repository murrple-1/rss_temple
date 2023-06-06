import shutil

from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.test import TestCase

from api.middleware import profiling


class ProfilingTestCase(TestCase):
    def test_middleware(self):
        with self.settings(
            PROFILING_OUTPUT_FILE="api/tests/test_files/profiling/profile", DEBUG=True
        ):
            middleware = profiling.ProfileMiddleware(lambda request: HttpResponse())

            request = HttpRequest()

            response = middleware(request)
            self.assertIsNotNone(response)

            request = HttpRequest()
            request.GET["_profile"] = "true"

            response = middleware(request)
            self.assertIsNotNone(response)

        with self.settings(PROFILING_OUTPUT_FILE=None, DEBUG=False):
            middleware = profiling.ProfileMiddleware(lambda request: HttpResponse())

            request = HttpRequest()

            response = middleware(request)
            self.assertIsNotNone(response)

        shutil.rmtree("api/tests/test_files/profiling/")
