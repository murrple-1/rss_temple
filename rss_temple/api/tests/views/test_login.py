import logging

from django.test import TestCase, Client

import ujson

from api import models
from api.password_hasher import password_hasher


class LoginTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('django').setLevel(logging.CRITICAL)

    def test_my_login_post(self):
        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
        }), 'application/json')
        self.assertEqual(response.status_code, 200)

    def test_my_login_post_email_missing(self):
        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'password': 'mypassword',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'missing', response.content)

    def test_my_login_post_email_typeerror(self):
        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': True,
            'password': 'mypassword',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'must be', response.content)

    def test_my_login_post_email_malformed(self):
        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': 'bademail',
            'password': 'mypassword',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'malformed', response.content)

    def test_my_login_post_password_missing(self):
        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': 'test@test.com',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'password', response.content)
        self.assertIn(b'missing', response.content)

    def test_my_login_post_password_typeerror(self):
        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': 'test@test.com',
            'password': True,
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'password', response.content)
        self.assertIn(b'must be', response.content)

    def test_my_login_post_already_exists(self):
        user = models.User.objects.create(email='test@test.com')

        models.MyLogin.objects.create(
            user=user, pw_hash=password_hasher().hash('mypassword'))

        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
        }), 'application/json')
        self.assertEqual(response.status_code, 409)

    def test_google_login_post(self):
        c = Client()

        with self.settings(GOOGLE_TEST_ID='googleid'):
            response = c.post('/api/login/google', ujson.dumps({
                'email': 'test@test.com',
                'password': 'mypassword',
                'token': 'goodtoken',
            }), 'application/json')
            self.assertEqual(response.status_code, 200)

    def test_google_login_post_duplicate_login(self):
        user1 = models.User.objects.create(email='test1@test.com')
        models.GoogleLogin.objects.create(g_user_id='googleid1', user=user1)

        user2 = models.User.objects.create(email='test2@test.com')
        models.MyLogin.objects.create(
            pw_hash=password_hasher().hash('password1'), user=user2)

        c = Client()

        with self.settings(GOOGLE_TEST_ID='googleid1'):
            response = c.post('/api/login/google', ujson.dumps({
                'email': 'test1@test.com',
                'password': 'mypassword',
                'token': 'goodtoken',
            }), 'application/json')
            self.assertEqual(response.status_code, 409)

        with self.settings(GOOGLE_TEST_ID='googleid'):
            response = c.post('/api/login/google', ujson.dumps({
                'email': 'test2@test.com',
                'password': 'mypassword',
                'token': 'goodtoken',
            }), 'application/json')
            self.assertEqual(response.status_code, 409)

    def test_google_login_post_email_missing(self):
        c = Client()
        response = c.post('/api/login/google', ujson.dumps({
            'password': 'mypassword',
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'missing', response.content)

    def test_google_login_post_email_typeerror(self):
        c = Client()
        response = c.post('/api/login/google', ujson.dumps({
            'email': True,
            'password': 'mypassword',
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'must be', response.content)

    def test_google_login_post_email_malformed(self):
        c = Client()
        response = c.post('/api/login/google', ujson.dumps({
            'email': 'bademail',
            'password': 'mypassword',
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'malformed', response.content)

    def test_google_login_post_password_missing(self):
        c = Client()
        response = c.post('/api/login/google', ujson.dumps({
            'email': 'test@test.com',
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'password', response.content)
        self.assertIn(b'missing', response.content)

    def test_google_login_post_password_typeerror(self):
        c = Client()
        response = c.post('/api/login/google', ujson.dumps({
            'email': 'test@test.com',
            'password': True,
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'password', response.content)
        self.assertIn(b'must be', response.content)

    def test_google_login_post_token_missing(self):
        c = Client()
        response = c.post('/api/login/google', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'token', response.content)
        self.assertIn(b'missing', response.content)

    def test_google_login_post_token_typeerror(self):
        c = Client()
        response = c.post('/api/login/google', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
            'token': True,
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'token', response.content)
        self.assertIn(b'must be', response.content)

    def test_facebook_login_post(self):
        c = Client()

        with self.settings(FACEBOOK_TEST_ID='facebookid'):
            response = c.post('/api/login/facebook', ujson.dumps({
                'email': 'test@test.com',
                'password': 'mypassword',
                'token': 'goodtoken',
            }), 'application/json')
            self.assertEqual(response.status_code, 200)

    def test_facebook_login_post_duplicate_login(self):
        user1 = models.User.objects.create(email='test1@test.com')
        models.FacebookLogin.objects.create(
            profile_id='facebookid1', user=user1)

        user2 = models.User.objects.create(email='test2@test.com')
        models.MyLogin.objects.create(
            pw_hash=password_hasher().hash('password1'), user=user2)

        c = Client()

        with self.settings(FACEBOOK_TEST_ID='facebookid1'):
            response = c.post('/api/login/facebook', ujson.dumps({
                'email': 'test1@test.com',
                'password': 'mypassword',
                'token': 'goodtoken',
            }), 'application/json')
            self.assertEqual(response.status_code, 409)

        with self.settings(FACEBOOK_TEST_ID='facebookid'):
            response = c.post('/api/login/facebook', ujson.dumps({
                'email': 'test2@test.com',
                'password': 'mypassword',
                'token': 'goodtoken',
            }), 'application/json')
            self.assertEqual(response.status_code, 409)

    def test_facebook_login_post_email_missing(self):
        c = Client()
        response = c.post('/api/login/facebook', ujson.dumps({
            'password': 'mypassword',
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'missing', response.content)

    def test_facebook_login_post_email_typeerror(self):
        c = Client()
        response = c.post('/api/login/facebook', ujson.dumps({
            'email': True,
            'password': 'mypassword',
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'must be', response.content)

    def test_facebook_login_post_email_malformed(self):
        c = Client()
        response = c.post('/api/login/facebook', ujson.dumps({
            'email': 'bademail',
            'password': 'mypassword',
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'malformed', response.content)

    def test_facebook_login_post_password_missing(self):
        c = Client()
        response = c.post('/api/login/facebook', ujson.dumps({
            'email': 'test@test.com',
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'password', response.content)
        self.assertIn(b'missing', response.content)

    def test_facebook_login_post_password_typeerror(self):
        c = Client()
        response = c.post('/api/login/facebook', ujson.dumps({
            'email': 'test@test.com',
            'password': True,
            'token': 'goodtoken',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'password', response.content)
        self.assertIn(b'must be', response.content)

    def test_facebook_login_post_token_missing(self):
        c = Client()
        response = c.post('/api/login/facebook', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'token', response.content)
        self.assertIn(b'missing', response.content)

    def test_facebook_login_post_token_typeerror(self):
        c = Client()
        response = c.post('/api/login/facebook', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
            'token': True,
        }), 'application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'token', response.content)
        self.assertIn(b'must be', response.content)

    def test_my_login_session_post(self):
        user = models.User.objects.create(email='test@test.com')

        models.MyLogin.objects.create(
            user=user, pw_hash=password_hasher().hash('mypassword'))

        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
        }), 'application/json')

        self.assertEqual(response.status_code, 200)

    def test_my_login_session_post_email_missing(self):
        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'password': 'mypassword',
        }), 'application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'missing', response.content)

    def test_my_login_session_post_email_typeerror(self):
        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': True,
            'password': 'mypassword',
        }), 'application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'email', response.content)
        self.assertIn(b'must be', response.content)

    def test_my_login_session_post_password_missing(self):
        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': 'test@test.com',
        }), 'application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'password', response.content)
        self.assertIn(b'missing', response.content)

    def test_my_login_session_post_password_typeerror(self):
        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': 'test@test.com',
            'password': True,
        }), 'application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'password', response.content)
        self.assertIn(b'must be', response.content)

    def test_my_login_session_post_no_user(self):
        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': 'bademail@test.com',
            'password': 'mypassword',
        }), 'application/json')

        self.assertEqual(response.status_code, 403)

    def test_my_login_session_post_bad_password(self):
        user = models.User.objects.create(email='test@test.com')

        models.MyLogin.objects.create(
            user=user, pw_hash=password_hasher().hash('mypassword'))

        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': 'test@test.com',
            'password': 'badpassword',
        }), 'application/json')

        self.assertEqual(response.status_code, 403)

    def test_google_login_session_post(self):
        user = models.User.objects.create(email='test@test.com')
        models.GoogleLogin.objects.create(user=user, g_user_id='googleid')

        c = Client()

        with self.settings(GOOGLE_TEST_ID='googleid'):
            response = c.post('/api/login/google/session', ujson.dumps({
                'token': 'goodtoken',
            }), 'application/json')

            self.assertEqual(response.status_code, 200)

    def test_google_login_session_post_create(self):
        c = Client()

        with self.settings(GOOGLE_TEST_ID='googleid'):
            response = c.post('/api/login/google/session', ujson.dumps({
                'token': 'goodtoken',
            }), 'application/json')

            self.assertEqual(response.status_code, 422)

            json_ = ujson.loads(response.content)

            self.assertIsInstance(json_, dict)
            self.assertIn('token', json_)
            self.assertIn('email', json_)
            self.assertIs(type(json_['token']), str)
            self.assertTrue(json_['email'] is None or type(
                json_['email']) is str)

    def test_google_login_session_post_token_missing(self):
        c = Client()
        response = c.post('/api/login/google/session',
                          ujson.dumps({}), 'application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'token', response.content)
        self.assertIn(b'missing', response.content)

    def test_google_login_session_post_token_typeerror(self):
        c = Client()
        response = c.post('/api/login/google/session', ujson.dumps({
            'token': True,
        }), 'application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'token', response.content)
        self.assertIn(b'must be', response.content)

    def test_facebook_login_session_post(self):
        user = models.User.objects.create(email='test@test.com')
        models.FacebookLogin.objects.create(user=user, profile_id='facebookid')

        c = Client()

        with self.settings(FACEBOOK_TEST_ID='facebookid'):
            response = c.post('/api/login/facebook/session', ujson.dumps({
                'token': 'goodtoken',
            }), 'application/json')

            self.assertEqual(response.status_code, 200)

    def test_facebook_login_session_post_create(self):
        c = Client()

        with self.settings(FACEBOOK_TEST_ID='facebookid'):
            response = c.post('/api/login/facebook/session', ujson.dumps({
                'token': 'goodtoken',
            }), 'application/json')

            self.assertEqual(response.status_code, 422)

            json_ = ujson.loads(response.content)

            self.assertIsInstance(json_, dict)
            self.assertIn('token', json_)
            self.assertIn('email', json_)
            self.assertIs(type(json_['token']), str)
            self.assertTrue(json_['email'] is None or type(
                json_['email']) is str)

    def test_facebook_login_session_post_token_missing(self):
        c = Client()
        response = c.post('/api/login/facebook/session',
                          ujson.dumps({}), 'application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'token', response.content)
        self.assertIn(b'missing', response.content)

    def test_facebook_login_session_post_token_typeerror(self):
        c = Client()
        response = c.post('/api/login/facebook/session', ujson.dumps({
            'token': True,
        }), 'application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'token', response.content)
        self.assertIn(b'must be', response.content)

    def test_session_delete(self):
        user = models.User.objects.create(email='test@test.com')

        session = models.Session.objects.create(user=user, expires_at=None)

        c = Client()

        response = c.delete('/api/session')
        self.assertEqual(response.status_code, 400)

        response = c.delete('/api/session', HTTP_X_SESSION_TOKEN='bad-uuid')
        self.assertEqual(response.status_code, 400)

        response = c.delete(
            '/api/session', HTTP_X_SESSION_TOKEN=str(session.uuid))
        self.assertEqual(response.status_code, 200)
