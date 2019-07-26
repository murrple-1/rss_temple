import logging

from django.test import TestCase, Client

import argon2

import ujson

from api import models

_password_hasher = argon2.PasswordHasher()


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

    def test_my_login_post_already_exists(self):
        user = models.User.objects.create(email='test@test.com')

        models.MyLogin.objects.create(user=user, pw_hash=_password_hasher.hash('mypassword'))

        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
        }), 'application/json')
        self.assertEqual(response.status_code, 409)

    def test_my_login_session_post(self):
        user = models.User.objects.create(email='test@test.com')

        models.MyLogin.objects.create(user=user, pw_hash=_password_hasher.hash('mypassword'))

        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
        }), 'application/json')

        self.assertEqual(response.status_code, 200)

    def test_my_login_session_post_no_user(self):
        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': 'bademail@test.com',
            'password': 'mypassword',
        }), 'application/json')

        self.assertEqual(response.status_code, 403)

    def test_my_login_session_post_bad_password(self):
        user = models.User.objects.create(email='test@test.com')

        models.MyLogin.objects.create(user=user, pw_hash=_password_hasher.hash('mypassword'))

        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': 'test@test.com',
            'password': 'badpassword',
        }), 'application/json')

        self.assertEqual(response.status_code, 403)

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
