from django.test.testcases import LiveServerTestCase, FSFilesHandler


class _TestFilesHandler(FSFilesHandler):
    def get_base_dir(self):
        return 'api/tests/test_files/'

    def get_base_url(self):
        return '/'


class TestFileServerTestCase(LiveServerTestCase):
    static_handler = _TestFilesHandler
