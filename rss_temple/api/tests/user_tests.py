from django.test import TestCase

from api import models, sorts

class UserTestCase(TestCase):
	__object_name = 'user'

	def setUp(self):
		models.User.objects.create(email='test2@test.com')
		models.User.objects.create(email='test1@test.com')
		models.User.objects.create(email='test3@test.com')

	def test_user_sort(self):
		sort_list = sorts.to_sort_list(UserTestCase.__object_name, 'email:DESC', False)
		db_sort_list = sorts.sort_list_to_db_sort_list(UserTestCase.__object_name, sort_list)

		sort = sorts.to_order_by_fields(db_sort_list)

		users = list(models.User.objects.order_by(*sort))

		self.assertEqual(users[0].email, 'test3@test.com')
		self.assertEqual(users[1].email, 'test2@test.com')
		self.assertEqual(users[2].email, 'test1@test.com')
