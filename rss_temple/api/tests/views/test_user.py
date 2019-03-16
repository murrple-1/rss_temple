import datetime
import logging

from django.test import TestCase, Client

import ujson

from api import models, fields


class UserTestCase(TestCase):
    # TODO
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('django').setLevel(logging.CRITICAL)

        try:
            cls.user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            cls.user = models.User.objects.create(
                email='test@test.com')

        cls.session = models.Session.objects.create(user=cls.user, expires_at=(
            datetime.datetime.utcnow() + datetime.timedelta(days=2)))

        cls.session_token = cls.session.uuid
        cls.session_token_str = str(cls.session.uuid)

    def test_user_get(self):
        c = Client()
        response = c.get('/api/user', {'fields': ','.join(fields.field_list(
            'user'))}, HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        _json = ujson.loads(response.content)

        self.assertTrue('subscribedFeedUuids' in _json)
