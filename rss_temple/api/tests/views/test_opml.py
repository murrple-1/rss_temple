import os
import logging
import datetime

from django.test import TestCase, Client

from api import models


class OPMLTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

        user = None
        try:
            user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User(email='test@test.com')
            user.save()

        cls.user = user

        session = models.Session(
            user=user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))
        session.save()

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

    def send_opml(self, client):
        text = None
        with open('api/tests/test_files/opml/opml.xml', 'r') as f:
            text = f.read()

        return client.post('/api/opml', text,
            content_type='text/xml', HTTP_X_SESSION_TOKEN=OPMLTestCase.session_token_str)

    def test_opml_get(self):
        c = Client()

        self.send_opml(c)

        response = c.get('/api/opml',
            HTTP_X_SESSION_TOKEN=OPMLTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)

    def test_opml_post(self):
        models.SubscribedFeedUserMapping.objects.filter(user=OPMLTestCase.user).delete()

        c = Client()
        response = self.send_opml(c)
        self.assertEqual(response.status_code, 200)
