import datetime
import logging
import uuid

from django.test import TestCase, Client
from django.db import IntegrityError

import ujson

from api import models, fields
from api.password_hasher import password_hasher


class UserTestCase(TestCase):
    USER_EMAIL = 'test@test.com'
    NON_UNIQUE_EMAIL = 'nonunique@test.com'
    UNIQUE_EMAIL = 'unique@test.com'

    USER_PASSWORD = 'password'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('django').setLevel(logging.CRITICAL)

        try:
            cls.user = models.User.objects.get(email=UserTestCase.USER_EMAIL)
        except models.User.DoesNotExist:
            cls.user = models.User.objects.create(
                email=UserTestCase.USER_EMAIL)

        try:
            models.MyLogin.objects.create(user=cls.user, pw_hash=password_hasher().hash(UserTestCase.USER_PASSWORD))
        except IntegrityError:
            pass

        cls.session = models.Session.objects.create(user=cls.user, expires_at=(
            datetime.datetime.utcnow() + datetime.timedelta(days=2)))

        cls.session_token = cls.session.uuid
        cls.session_token_str = str(cls.session.uuid)

        user2 = None
        try:
            user2 = models.User.objects.create(email=UserTestCase.NON_UNIQUE_EMAIL)
            models.MyLogin.objects.create(user=user2, pw_hash=password_hasher().hash('password2'))
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
                    'old': UserTestCase.USER_PASSWORD,
                },
            },
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'my': {
                'password': {
                    'old': UserTestCase.USER_PASSWORD,
                    'new': None,
                },
            },
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

        body = {
            'my': {
                'password': {
                    'old': 'badpassword',
                    'new': 'newpassword',
                },
            },
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 403)

        body = {
            'my': {
                'password': {
                    'old': UserTestCase.USER_PASSWORD,
                    'new': 'newpassword',
                },
            },
        }
        response = c.put('/api/user', ujson.dumps(body),
            content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        my_login = UserTestCase.user.my_login()
        my_login.pw_hash = password_hasher().hash(UserTestCase.USER_PASSWORD)
        my_login.save()

    def test_user_verify_post(self):
        c = Client()

        response = c.post('/api/user/verify')
        self.assertEqual(response.status_code, 400)

        params = {
            'token': 'BAD_TOKEN',
        }
        response = c.post('/api/user/verify', params)
        self.assertEqual(response.status_code, 404)

        params = {
            'token': str(uuid.uuid4()),
        }
        response = c.post('/api/user/verify', params)
        self.assertEqual(response.status_code, 404)

        verification_token = models.VerificationToken.objects.create(expires_at=(
            datetime.datetime.utcnow() + datetime.timedelta(days=2)), user=UserTestCase.user)

        params = {
            'token': verification_token.token_str(),
        }
        response = c.post('/api/user/verify', params)
        self.assertEqual(response.status_code, 200)
