import unittest
import time

from django.conf import settings
from django.test.runner import DiscoverRunner


class DjangoTimedTestRunner(DiscoverRunner):
    def get_resultclass(self):
        return TimeLoggingTestResult


class TimeLoggingTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        self.slow_test_threshold = getattr(settings, 'TEST_SLOW_TEST_THRESHOLD', 0.3)
        super().__init__(stream, descriptions, verbosity)

    def startTest(self, test):
        self._started_at = time.time()
        super().startTest(test)

    def addSuccess(self, test):
        elapsed = time.time() - self._started_at
        if elapsed > self.slow_test_threshold:
            name = self.getDescription(test)
            self.stream.write('\n{} ({:.03}s)\n'.format(name, elapsed))
        super().addSuccess(test)
