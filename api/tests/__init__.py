from django.test.testcases import FSFilesHandler
from rest_framework.test import APILiveServerTestCase


class _TestFilesHandler(FSFilesHandler):
    def get_base_dir(self):
        return "api/tests/test_files/"

    def get_base_url(self):
        return "/"


class TestFileServerTestCase(APILiveServerTestCase):
    static_handler = _TestFilesHandler
