import datetime

from django.test import TestCase, Client

import ujson

from api import models

class LoginTestCase(TestCase):
    # TODO
    def test_my_login_post(self):
        c = Client()
        response = c.post('/api/login/my', ujson.dumps({
            'email': 'someemail@test.com',
            'password': 'mypassword',
            }), 'application/json')
        self.assertEqual(response.status_code, 200)
