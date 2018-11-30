import logging
import datetime

from django.test import TestCase, Client

from api import models


class UserCategoryTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)
        logging.getLogger('django').setLevel(logging.CRITICAL)

        try:
            cls.user = models.User.objects.get(email='test@test.com')
        except models.User.DoesNotExist:
            cls.user = models.User(email='test@test.com')
            cls.user.save()

        session = models.Session(
            user=cls.user, expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2))
        session.save()

        cls.session = session

        cls.session_token = session.uuid
        cls.session_token_str = str(session.uuid)

    def test_usercategory_get(self):
        models.UserCategory.objects.all().delete()

        user_category = None
        try:
            user_category = models.UserCategory.objects.get(user=UserCategoryTestCase.user, text='Test User Category')
        except models.UserCategory.DoesNotExist:
            user_category = models.UserCategory(
                user=UserCategoryTestCase.user, text='Test User Category')
            user_category.save()

        c = Client()

        response = c.get('/api/usercategory/{}'.format(str(user_category.uuid)),
            HTTP_X_SESSION_TOKEN=UserCategoryTestCase.session_token_str)
        self.assertEqual(response.status_code, 200)
