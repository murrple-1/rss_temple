from typing import ClassVar

from django.test import TestCase
from throttle import zones


class ViewTestCase(TestCase):
    old_throttle_enabled: ClassVar[bool]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_throttle_enabled = zones.THROTTLE_ENABLED
        zones.THROTTLE_ENABLED = False

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        zones.THROTTLE_ENABLED = cls.old_throttle_enabled
