import datetime
import logging

from django.test import TestCase

from api import models

from daemons.session_cleanup_daemon import cleanup


class DaemonTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('session_cleanup_daemon').setLevel(logging.CRITICAL)

        try:
            cls.user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            cls.user = models.User.objects.create(email='test@test.com')

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

        models.Session.objects.create(expires_at=datetime.datetime.utcnow() +
                       datetime.timedelta(days=-1), user=user)

        models.Session.objects.create(expires_at=datetime.datetime.utcnow() +
                       datetime.timedelta(days=1), user=user)

        self.assertEquals(models.Session.objects.filter(user=user).count(), 2)

        cleanup()

        self.assertEquals(models.Session.objects.filter(user=user).count(), 1)
