import uuid
import datetime
import logging

from django.test import TestCase

from api import fields, models
from api.context import Context


class _ObjectConfig:
    def __init__(self, object_name, all_count, default_count, good_field_name, bad_field_name='bad_field_name'):
        self.object_name = object_name
        self.all_count = all_count
        self.default_count = default_count
        self.good_field_name = good_field_name
        self.bad_field_name = bad_field_name


_object_configs = [
    _ObjectConfig('user', 3, 1, 'uuid'),
    _ObjectConfig('feed', 9, 1, 'uuid'),
    _ObjectConfig('feedentry', 12, 1, 'uuid'),
    _ObjectConfig('usercategory', 3, 2, 'uuid'),
]


class FieldsTestCase(TestCase):
    def test_default_field_maps(self):
        for oc in _object_configs:
            default_field_maps = fields.get_default_field_maps(oc.object_name)

            self.assertEquals(len(default_field_maps), oc.default_count)

            for field_map in default_field_maps:
                self.assertIn('field_name', field_map)
                self.assertIsInstance(field_map['field_name'], str)
                self.assertIn('accessor', field_map)
                self.assertTrue(callable(field_map['accessor']))

    def test_all_field_maps(self):
        for oc in _object_configs:
            all_field_maps = fields.get_all_field_maps(oc.object_name)

            self.assertEquals(len(all_field_maps), oc.all_count)

            for field_map in all_field_maps:
                self.assertIn('field_name', field_map)
                self.assertIsInstance(field_map['field_name'], str)
                self.assertIn('accessor', field_map)
                self.assertTrue(callable(field_map['accessor']))

    def test_fieldconfig(self):
        fc = fields._FieldConfig(lambda context, db_obj: 'test', True)

        self.assertEquals(fc.accessor(object(), object()), 'test')
        self.assertTrue(fc.default)

        with self.assertRaises(TypeError):
            fields._FieldConfig(None, None)

        with self.assertRaises(TypeError):
            fields._FieldConfig(lambda: None, None)

    def test_to_field_map(self):
        for oc in _object_configs:
            field_map = fields.to_field_map(oc.object_name, oc.good_field_name)

            self.assertEquals(field_map['field_name'], oc.good_field_name)

            class TestContext:
                pass

            class TestObject:
                def __init__(self):
                    self.uuid = uuid.uuid4()

            test_context = TestContext()
            test_obj = TestObject()
            self.assertIsInstance(field_map['accessor'](
                test_context, test_obj), str)

            field_map = fields.to_field_map(oc.object_name, oc.bad_field_name)
            self.assertIsNone(field_map)


class AllFieldsTestCase(TestCase):
    @classmethod
    def generate_users(cls):
        return [cls.user]

    @classmethod
    def generate_usercategories(cls):
        return [cls.user_category]

    @classmethod
    def generate_feeds(cls):
        return [cls.feed_with_category, cls.feed_without_category]

    @classmethod
    def generate_feedentries(cls):
        return [cls.feed_entry]

    class MockRequest:
            def __init__(self):
                self.user = AllFieldsTestCase.user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)

        cls.TRIALS = {
            'user': AllFieldsTestCase.generate_users,
            'usercategory': AllFieldsTestCase.generate_usercategories,
            'feed': AllFieldsTestCase.generate_feeds,
            'feedentry': AllFieldsTestCase.generate_feedentries,
        }

        models.User.objects.all().delete()
        models.UserCategory.objects.all().delete()
        models.Feed.objects.all().delete()
        models.FeedEntry.objects.all().delete()

        cls.user = models.User(
            email='test_fields@test.com')
        cls.user.save()

        cls.user_category = models.UserCategory(
            user=cls.user, text='Test Category')
        cls.user_category.save()

        cls.feed_with_category = models.Feed(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)
        cls.feed_with_category.save()

        cls.feed_without_category = models.Feed(
            feed_url='http://example2.com/rss.xml',
            title='Sample Feed 2',
            home_url='http://example2.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)
        cls.feed_without_category.save()

        cls.feed_entry = models.FeedEntry(
            feed=cls.feed_with_category,
            url='http://example.com/entry1.html',
            content='<b>Some HTML Content</b>',
            author_name='John Doe')
        cls.feed_entry.hash = hash(cls.feed_entry)
        cls.feed_entry.save()

        subscription1 = models.SubscribedFeedUserMapping(
            feed=cls.feed_with_category, user=cls.user, custom_feed_title='Custom Title 1')
        subscription1.save()

        subscription2 = models.SubscribedFeedUserMapping(
            feed=cls.feed_without_category, user=cls.user, custom_feed_title=None)
        subscription2.save()

        user_category_mapping = models.FeedUserCategoryMapping(
            feed=cls.feed_with_category, user_category=cls.user_category)
        user_category_mapping.save()

    def test_run(self):
        self.assertEqual(len(AllFieldsTestCase.TRIALS), len(fields._field_configs))

        for key, generator in AllFieldsTestCase.TRIALS.items():
            db_objs = generator()

            fields_dict = fields._field_configs[key]

            for db_obj in db_objs:
                for field_config in fields_dict.values():
                    context = Context()
                    context.request = AllFieldsTestCase.MockRequest()

                    field_config.accessor(context, db_obj)
