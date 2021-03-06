import datetime
import logging
import uuid

from django.test import TestCase, Client

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

        cls.old_django_logger_level = logging.getLogger('django').getEffectiveLevel()

        logging.getLogger('django').setLevel(logging.CRITICAL)

        cls.user = models.User.objects.create(email=UserTestCase.USER_EMAIL)
        models.MyLogin.objects.create(
            user=cls.user, pw_hash=password_hasher().hash(UserTestCase.USER_PASSWORD))

        cls.session = models.Session.objects.create(user=cls.user, expires_at=(
            datetime.datetime.utcnow() + datetime.timedelta(days=2)))

        cls.session_token = cls.session.uuid
        cls.session_token_str = str(cls.session.uuid)

        user2 = models.User.objects.create(
            email=UserTestCase.NON_UNIQUE_EMAIL)
        models.MyLogin.objects.create(
            user=user2, pw_hash=password_hasher().hash('password2'))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger('django').setLevel(cls.old_django_logger_level)

    def test_user_get(self):
        c = Client()
        response = c.get('/api/user', {'fields': ','.join(fields.field_list(
            'user'))}, HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        json_ = ujson.loads(response.content)

        self.assertIn('subscribedFeedUuids', json_)

    def test_user_put_email(self):
        body = {
            'email': UserTestCase.UNIQUE_EMAIL,
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(models.User.objects.filter(
            uuid=UserTestCase.user.uuid, email=UserTestCase.USER_EMAIL).count(), 0)
        self.assertEqual(models.User.objects.filter(
            uuid=UserTestCase.user.uuid, email=UserTestCase.UNIQUE_EMAIL).count(), 1)

    def test_user_put_email_sameasbefore(self):
        body = {
            'email': UserTestCase.USER_EMAIL,
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(models.User.objects.filter(
            uuid=UserTestCase.user.uuid, email=UserTestCase.USER_EMAIL).count(), 1)

    def test_user_put_email_typeerror(self):
        body = {
            'email': 1,
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_email_empty(self):
        body = {
            'email': '',
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_email_malformed(self):
        body = {
            'email': 'malformed',
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_email_nonunique(self):
        body = {
            'email': UserTestCase.NON_UNIQUE_EMAIL,
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 409)

    def test_user_put_my(self):
        body = {
            'my': {},
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_user_put_my_typeerror(self):
        body = {
            'my': None,
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_my_password(self):
        body = {
            'my': {
                'password': {
                    'old': UserTestCase.USER_PASSWORD,
                    'new': 'newpassword',
                },
            },
        }

        old_pw_hash = models.MyLogin.objects.get(
            user=UserTestCase.user).pw_hash

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        new_pw_hash = models.MyLogin.objects.get(
            user=UserTestCase.user).pw_hash

        self.assertNotEqual(old_pw_hash, new_pw_hash)

    def test_user_put_my_password_typeerror(self):
        body = {
            'my': {
                'password': None,
            },
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_my_password_old_missing(self):
        body = {
            'my': {
                'password': {
                    'new': 'newpassword',
                },
            },
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_my_password_old_typeerror(self):
        body = {
            'my': {
                'password': {
                    'old': None,
                    'new': 'newpassword',
                },
            },
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_my_password_new_missing(self):
        body = {
            'my': {
                'password': {
                    'old': UserTestCase.USER_PASSWORD,
                },
            },
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_my_password_new_typeerror(self):
        body = {
            'my': {
                'password': {
                    'old': UserTestCase.USER_PASSWORD,
                    'new': None,
                },
            },
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_my_password_badoldpassword(self):
        body = {
            'my': {
                'password': {
                    'old': 'badpassword',
                    'new': 'newpassword',
                },
            },
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 403)

    def test_user_put_google(self):
        body = {
            'google': {},
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_user_put_google_typeerror(self):
        body = {
            'google': 1,
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_google_create(self):
        self.assertEqual(models.GoogleLogin.objects.filter(
            user=UserTestCase.user).count(), 0)

        body = {
            'google': {
                'token': 'goodtoken',
            },
        }

        c = Client()
        with self.settings(GOOGLE_TEST_ID='googleid'):
            response = c.put('/api/user', ujson.dumps(body),
                             content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
            self.assertEqual(response.status_code, 200)

        self.assertEqual(models.GoogleLogin.objects.filter(
            user=UserTestCase.user).count(), 1)

    def test_user_put_google_delete(self):
        models.GoogleLogin.objects.create(
            user=UserTestCase.user, g_user_id='googleid')
        self.assertEqual(models.GoogleLogin.objects.filter(
            user=UserTestCase.user).count(), 1)

        body = {
            'google': None,
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(models.GoogleLogin.objects.filter(
            user=UserTestCase.user).count(), 0)

    def test_user_put_google_token_typeerror(self):
        body = {
            'google': {
                'token': None,
            },
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_facebook(self):
        body = {
            'facebook': {},
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_user_put_facebook_typeerror(self):
        body = {
            'facebook': 1,
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_put_facebook_create(self):
        self.assertEqual(models.FacebookLogin.objects.filter(
            user=UserTestCase.user).count(), 0)

        body = {
            'facebook': {
                'token': 'goodtoken',
            },
        }

        c = Client()
        with self.settings(FACEBOOK_TEST_ID='facebookid'):
            response = c.put('/api/user', ujson.dumps(body),
                             content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
            self.assertEqual(response.status_code, 200)

        self.assertEqual(models.FacebookLogin.objects.filter(
            user=UserTestCase.user).count(), 1)

    def test_user_put_facebook_delete(self):
        models.FacebookLogin.objects.create(
            user=UserTestCase.user, profile_id='facebookid')
        self.assertEqual(models.FacebookLogin.objects.filter(
            user=UserTestCase.user).count(), 1)

        body = {
            'facebook': None,
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(models.FacebookLogin.objects.filter(
            user=UserTestCase.user).count(), 0)

    def test_user_put_facebook_token_typeerror(self):
        body = {
            'facebook': {
                'token': None,
            },
        }

        c = Client()
        response = c.put('/api/user', ujson.dumps(body),
                         content_type='application/json', HTTP_X_SESSION_TOKEN=UserTestCase.session_token_str)
        self.assertEqual(response.status_code, 400)

    def test_user_verify_post(self):
        verification_token = models.VerificationToken.objects.create(expires_at=(
            datetime.datetime.utcnow() + datetime.timedelta(days=2)), user=UserTestCase.user)

        params = {
            'token': verification_token.token_str(),
        }
        c = Client()
        response = c.post('/api/user/verify', params)
        self.assertEqual(response.status_code, 200)

    def test_user_verify_post_token_missing(self):
        c = Client()
        response = c.post('/api/user/verify')
        self.assertEqual(response.status_code, 400)

    def test_user_verify_post_token_malformed(self):
        params = {
            'token': 'BAD_TOKEN',
        }
        c = Client()
        response = c.post('/api/user/verify', params)
        self.assertEqual(response.status_code, 404)

    def test_user_verify_post_token_notfound(self):
        params = {
            'token': str(uuid.uuid4()),
        }
        c = Client()
        response = c.post('/api/user/verify', params)
        self.assertEqual(response.status_code, 404)
