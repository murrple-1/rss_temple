import datetime
import logging
import uuid

from django.test import TestCase, Client
from django.db import IntegrityError

from api import models
from api.password_hasher import password_hasher


class UserTestCase(TestCase):
    USER_EMAIL = 'test@test.com'

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
            models.MyLogin.objects.create(
                user=cls.user, pw_hash=password_hasher().hash(UserTestCase.USER_PASSWORD))
        except IntegrityError:
            pass

    def test_passwordresettoken_request_post(self):
        c = Client()

        response = c.post('/api/passwordresettoken/request')
        self.assertEqual(response.status_code, 400)

        params = {}
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 400)

        params = {
            'email': '',
        }
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 200)

        params = {
            'email': 'malformedemail',
        }
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 200)

        params = {
            'email': 'unknownemail@test.com',
        }
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 200)

        params = {
            'email': UserTestCase.USER_EMAIL,
        }
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 200)

    def test_passwordresettoken_reset_post(self):
        c = Client()

        response = c.post('/api/passwordresettoken/reset')
        self.assertEqual(response.status_code, 400)

        params = {}
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 400)

        params = {
            'token': '',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 400)

        params = {
            'token': '',
            'password': '',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 404)

        params = {
            'token': 'badtoken',
            'password': 'newpassword',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 404)

        params = {
            'token': str(uuid.uuid4()),
            'password': 'newpassword',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 404)

        password_reset_token = models.PasswordResetToken.objects.create(expires_at=(
            datetime.datetime.utcnow() + datetime.timedelta(days=2)), user=UserTestCase.user)

        params = {
            'token': password_reset_token.token_str(),
            'password': 'newpassword',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 200)

        my_login = UserTestCase.user.my_login()
        my_login.pw_hash = password_hasher().hash(UserTestCase.USER_PASSWORD)
        my_login.save()
