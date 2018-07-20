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

        user = None
        try:
            user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User(
                email='test@test.com')

            user.save()

        cls.user = user

        session = models.Session()
        session.user = user
        session.expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=2))

        session.save()

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

    def test_user_get(self):
        c = Client()
        response = c.get('/api/user', { 'fields': ','.join(fields.field_list('user')) }, HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        _json = ujson.loads(response.content)

        self.assertTrue('subscribedFeedUuids' in _json)
