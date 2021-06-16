import datetime
import logging
import uuid

from django.test import TestCase, Client

from api import models
from api.password_hasher import password_hasher


class UserTestCase(TestCase):
    USER_EMAIL = 'test@test.com'

    USER_PASSWORD = 'password'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_django_logger_level = logging.getLogger(
            'django').getEffectiveLevel()

        logging.getLogger('django').setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger('django').setLevel(cls.old_django_logger_level)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = models.User.objects.create(email=UserTestCase.USER_EMAIL)

        models.MyLogin.objects.create(
            user=cls.user, pw_hash=password_hasher().hash(UserTestCase.USER_PASSWORD))

    def test_passwordresettoken_request_post(self):
        c = Client()

        response = c.post('/api/passwordresettoken/request')
        self.assertEqual(response.status_code, 400, response.content)

        params = {}
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            'email': '',
        }
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 204, response.content)

        params = {
            'email': 'malformedemail',
        }
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 204, response.content)

        params = {
            'email': 'unknownemail@test.com',
        }
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 204, response.content)

        params = {
            'email': UserTestCase.USER_EMAIL,
        }
        response = c.post('/api/passwordresettoken/request', params)
        self.assertEqual(response.status_code, 204, response.content)

    def test_passwordresettoken_reset_post(self):
        c = Client()

        response = c.post('/api/passwordresettoken/reset')
        self.assertEqual(response.status_code, 400, response.content)

        params = {}
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            'token': '',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 400, response.content)

        params = {
            'token': '',
            'password': '',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 404, response.content)

        params = {
            'token': 'badtoken',
            'password': 'newpassword',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 404, response.content)

        params = {
            'token': str(uuid.uuid4()),
            'password': 'newpassword',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 404, response.content)

        password_reset_token = models.PasswordResetToken.objects.create(expires_at=(
            datetime.datetime.utcnow() + datetime.timedelta(days=2)), user=UserTestCase.user)

        params = {
            'token': password_reset_token.token_str(),
            'password': 'newpassword',
        }
        response = c.post('/api/passwordresettoken/reset', params)
        self.assertEqual(response.status_code, 204, response.content)
