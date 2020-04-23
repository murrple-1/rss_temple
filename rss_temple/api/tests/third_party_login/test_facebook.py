import unittest
import os

from django.test import TestCase
from django.http import HttpRequest

from api.third_party_login import facebook

@unittest.skipIf(not {'TEST_REMOTE', 'TEST_FACEBOOK_TOKEN'}.issubset(frozenset(os.environ)), '`TEST_REMOTE`, and `TEST_FACEBOOK_TOKEN` env var(s) must be set: remote test')
class FacebookTestCase(TestCase):
    def test_get_id(self):
        profile_id = facebook.get_id(os.environ['TEST_FACEBOOK_TOKEN'])
        self.assertIsInstance(profile_id, str)

    def test_get_id_badtoken(self):
        with self.assertRaises(ValueError):
            facebook.get_id('badtoken')

    def test_get_id_and_email(self):
        profile_id, email = facebook.get_id_and_email(os.environ['TEST_FACEBOOK_TOKEN'])
        self.assertIsInstance(profile_id, str)
        self.assertTrue(email is None or type(email) is str)

    def test_get_id_and_email_badtoken(self):
        with self.assertRaises(ValueError):
            facebook.get_id_and_email('badtoken')
