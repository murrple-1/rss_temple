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
        models.User.objects.filter(
            email='test@test.com').delete()

        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
            }), 'application/json')
        self.assertEqual(response.status_code, 200)

    def test_my_login_post_already_exists(self):
        user = None
        try:
            user = models.User.objects.get(
                email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User(
                email='test@test.com')
            user.save()

        my_login = None
        try:
            my_login = models.MyLogin.objects.get(user=user)
        except models.MyLogin.DoesNotExist:
            my_login = models.MyLogin(
                user=user,
                pw_hash=_password_hasher.hash('mypassword'))
            my_login.save()

        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': 'test@test.com',
            'password': 'mypassword',
            }), 'application/json')
        self.assertEqual(response.status_code, 409)

    def test_my_login_session_post(self):
        user = None
        try:
            user = models.User.objects.get(
                email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User(
                email='test@test.com')
            user.save()

        my_login = None
        try:
            my_login = models.MyLogin.objects.get(user=user)
        except models.MyLogin.DoesNotExist:
            my_login = models.MyLogin(
                user=user,
                pw_hash=_password_hasher.hash('mypassword'))
            my_login.save()

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
        user = None
        try:
            user = models.User.objects.get(
                email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User(
                email='test@test.com')
            user.save()

        my_login = None
        try:
            my_login = models.MyLogin.objects.get(user=user)
        except models.MyLogin.DoesNotExist:
            my_login = models.MyLogin(
                user=user,
                pw_hash=_password_hasher.hash('mypassword'))
            my_login.save()

        c = Client()
        response = c.post('/api/login/my/session', ujson.dumps({
            'email': 'test@test.com',
            'password': 'badpassword',
            }), 'application/json')

        self.assertEqual(response.status_code, 403)
