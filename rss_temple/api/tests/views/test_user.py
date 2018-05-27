import datetime

from django.test import TestCase, Client

from api import models

class UserTestCase(TestCase):
    # TODO
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        user = None
        try:
            user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            user = models.User()
            user.email = 'test@test.com'

            user.save()

        session = models.Session()
        session.user = user
        session.expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=2))

        session.save()

        cls.session_token = str(session.uuid)

    def test_user_get(self):
        c = Client()
        response = c.get('/api/user', { 'fields': '_all' }, HTTP_X_SESSION_TOKEN=UserTestCase.session_token)
        self.assertEqual(response.status_code, 200)
