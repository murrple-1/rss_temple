import datetime
import logging

from django.test import TestCase

import api.models as models
from api.session_cleanup_daemon import cleanup


class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('session_cleanup_daemon').setLevel(logging.CRITICAL)

        cls.user = models.User(email='example@example.com')
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        cls.user.delete()

    def test_none(self):
        user = DaemonTestCase.user

        models.Session.objects.filter(user=user).delete()

        self.assertEquals(models.Session.objects.filter(user=user).count(), 0)

        cleanup()

        self.assertEquals(models.Session.objects.filter(user=user).count(), 0)

    def test_some(self):
        user = DaemonTestCase.user

        models.Session.objects.filter(user=user).delete()

        self.assertEquals(models.Session.objects.filter(user=user).count(), 0)

        models.Session(expires_at=datetime.datetime.utcnow() +
                       datetime.timedelta(days=-1), user=user).save()

        models.Session(expires_at=datetime.datetime.utcnow() +
                       datetime.timedelta(days=1), user=user).save()

        self.assertEquals(models.Session.objects.filter(user=user).count(), 2)

        cleanup()

        self.assertEquals(models.Session.objects.filter(user=user).count(), 1)
