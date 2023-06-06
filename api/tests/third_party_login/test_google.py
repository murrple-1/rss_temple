import os
import unittest

from django.test import TestCase, tag

from api.third_party_login import google

# To get a testable Client ID and Access Token,
# go to: https://developers.google.com/oauthplayground/
# Manually type `email` into "Input your own scopes" and press "Authorize APIs"
# Click through the consent screen
# Click "Exchange authorization code for tokens"
# In the Request, get the Client ID from the query param `id_token`
# In the Response, get the Access Token from the JSON field `access_token`
# Note that the access token expires pretty quickly, so you'll have to regenerate pretty frequently


@tag("remote")
@unittest.skipIf(
    not {"TEST_GOOGLE_TOKEN", "GOOGLE_CLIENT_ID"}.issubset(
        frozenset(os.environ.keys())
    ),
    "`TEST_GOOGLE_TOKEN`, and `GOOGLE_CLIENT_ID` env var(s) must be set",
)
class GoogleTestCase(TestCase):
    def test_get_id(self):
        g_user_id = google.get_id(os.environ["TEST_GOOGLE_TOKEN"])
        self.assertIsInstance(g_user_id, str)

    def test_get_id_badtoken(self):
        with self.assertRaises(ValueError):
            google.get_id("badtoken")

    def test_get_id_and_email(self):
        g_user_id, email = google.get_id_and_email(os.environ["TEST_GOOGLE_TOKEN"])
        self.assertIsInstance(g_user_id, str)
        self.assertTrue(email is None or type(email) is str)

    def test_get_id_and_email_badtoken(self):
        with self.assertRaises(ValueError):
            google.get_id_and_email("badtoken")
