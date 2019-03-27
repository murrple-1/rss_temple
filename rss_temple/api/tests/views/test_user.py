import datetime
import logging

from django.test import TestCase, Client
from django.db import IntegrityError

import ujson

from api import models, fields


class UserTestCase(TestCase):
    USER_EMAIL = 'test@test.com'
    NON_UNIQUE_EMAIL = 'nonunique@test.com'
    UNIQUE_EMAIL = 'unique@test.com'

    # TODO
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('django').setLevel(logging.CRITICAL)

        try:
            cls.user = models.User.objects.get(email=UserTestCase.USER_EMAIL)
        except models.User.DoesNotExist:
            cls.user = models.User.objects.create(
                email=UserTestCase.USER_EMAIL)

        cls.session = models.Session.objects.create(user=cls.user, expires_at=(
            datetime.datetime.utcnow() + datetime.timedelta(days=2)))

        cls.session_token = cls.session.uuid
        cls.session_token_str = str(cls.session.uuid)

        try:
            models.User.objects.create(email=UserTestCase.NON_UNIQUE_EMAIL)
        except IntegrityError:
            logging.getLogger(__name__).exception('unable to create non-unique user...this isn\'t expected')

    def test_user_get(self):
        c = Client()
        response = c.get('/api/user', {'fields': ','.join(fields.field_list(
            'user'))}, HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        _json = ujson.loads(response.content)

        self.assertTrue('subscribedFeedUuids' in _json)

    def test_user_put(self):
        c = Client()

        body = {
            'email': 1,
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'email': '',
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'email': 'malformed',
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'email': UserTestCase.USER_EMAIL,
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        body = {
            'email': UserTestCase.NON_UNIQUE_EMAIL,
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 409)

        body = {
            'email': UserTestCase.UNIQUE_EMAIL,
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        UserTestCase.user.email = UserTestCase.USER_EMAIL
        UserTestCase.user.save()

        body = {
            'my': None,
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'my': {
                'password': None,
            },
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'my': {
                'password': {},
            },
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'my': {
                'password': {
                    'old': None,
                },
            },
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'my': {
                'password': {
                    'old': 'oldpassword',
                },
            },
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'my': {
                'password': {
                    'old': 'oldpassword',
                    'new': None,
                },
            },
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)
