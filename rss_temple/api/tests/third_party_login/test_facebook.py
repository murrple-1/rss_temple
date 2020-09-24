import unittest
import os

from django.test import TestCase

from api.third_party_login import facebook

# To get a testable Acess Token,
# go to: https://developers.facebook.com/
# Find the test app under "My Apps"
# Go to Roles > Test Users
# Create a test user if none exist, ensure it has ["email"] Login Permissions
# On the user, click "Edit", then "Get an access token for this test user"
# Copy the Access Token after it loads
# Note that the access token expires pretty quickly, so you'll have to regenerate pretty frequently
@unittest.skipIf(not {'TEST_REMOTE', 'TEST_FACEBOOK_TOKEN'}.issubset(frozenset(os.environ.keys())), '`TEST_REMOTE`, and `TEST_FACEBOOK_TOKEN` env var(s) must be set: remote test')
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
