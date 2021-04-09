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
    _ObjectConfig('user', 5, 1, 'uuid'),
    _ObjectConfig('feed', 12, 1, 'uuid'),
    _ObjectConfig('feedentry', 14, 1, 'uuid'),
    _ObjectConfig('usercategory', 3, 2, 'uuid'),
    _ObjectConfig('tag', 2, 2, 'uuid'),
]


class FieldsTestCase(TestCase):
    def test_default_field_maps(self):
        for oc in _object_configs:
            default_field_maps = fields.get_default_field_maps(oc.object_name)

            self.assertEqual(len(default_field_maps), oc.default_count)

            for field_map in default_field_maps:
                self.assertIn('field_name', field_map)
                self.assertIs(type(field_map['field_name']), str)
                self.assertIn('accessor', field_map)
                self.assertTrue(callable(field_map['accessor']))

    def test_all_field_maps(self):
        for oc in _object_configs:
            all_field_maps = fields.get_all_field_maps(oc.object_name)

            self.assertEqual(len(all_field_maps), oc.all_count)

            for field_map in all_field_maps:
                self.assertIn('field_name', field_map)
                self.assertIs(type(field_map['field_name']), str)
                self.assertIn('accessor', field_map)
                self.assertTrue(callable(field_map['accessor']))

    def test_fieldconfig(self):
        fc = fields._FieldConfig(lambda context, db_obj: 'test', True)

        self.assertEqual(fc.accessor(object(), object()), 'test')
        self.assertTrue(fc.default)

        with self.assertRaises(TypeError):
            fields._FieldConfig(None, None)

        with self.assertRaises(TypeError):
            fields._FieldConfig(lambda: None, None)

    def test_to_field_map(self):
        for oc in _object_configs:
            field_map = fields.to_field_map(oc.object_name, oc.good_field_name)

            self.assertEqual(field_map['field_name'], oc.good_field_name)

            class TestContext:
                pass

            class TestObject:
                def __init__(self):
                    self.uuid = uuid.uuid4()

            test_context = TestContext()
            test_obj = TestObject()
            self.assertIs(type(field_map['accessor'](
                test_context, test_obj)), str)

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
        feeds = [cls.feed_with_category, cls.feed_without_category]

        for feed in feeds:
            feed.custom_title = None
            feed.is_subscribed = False

        return feeds

    @classmethod
    def generate_feedentries(cls):
        return [cls.feed_entry]

    @classmethod
    def generate_tags(cls):
        return [cls.tag]

    class MockRequest:
        def __init__(self):
            self.user = AllFieldsTestCase.user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_logger_level = logging.getLogger(
            'rss_temple').getEffectiveLevel()

        logging.getLogger('rss_temple').setLevel(logging.CRITICAL)

        cls.TRIALS = {
            'user': AllFieldsTestCase.generate_users,
            'usercategory': AllFieldsTestCase.generate_usercategories,
            'feed': AllFieldsTestCase.generate_feeds,
            'feedentry': AllFieldsTestCase.generate_feedentries,
            'tag': AllFieldsTestCase.generate_tags,
        }

        cls.user = models.User.objects.create(
            email='test_fields@test.com')

        cls.user_category = models.UserCategory.objects.create(
            user=cls.user, text='Test Category')

        cls.feed_with_category = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        cls.feed_without_category = models.Feed.objects.create(
            feed_url='http://example2.com/rss.xml',
            title='Sample Feed 2',
            home_url='http://example2.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        cls.feed_entry = models.FeedEntry.objects.create(
            feed=cls.feed_with_category,
            url='http://example.com/entry1.html',
            content='<b>Some HTML Content</b>',
            author_name='John Doe')

        models.SubscribedFeedUserMapping.objects.create(
            feed=cls.feed_with_category, user=cls.user, custom_feed_title='Custom Title 1')

        models.SubscribedFeedUserMapping.objects.create(
            feed=cls.feed_without_category, user=cls.user, custom_feed_title=None)

        models.FeedUserCategoryMapping.objects.create(
            feed=cls.feed_with_category, user_category=cls.user_category)

        cls.tag = models.Tag.objects.create(label_text='Tag')
        models.FeedTagMapping.objects.create(tag=cls.tag, feed=cls.feed_with_category)
        models.FeedTagMapping.objects.create(tag=cls.tag, feed=cls.feed_without_category)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger('rss_temple').setLevel(cls.old_logger_level)

    def test_run(self):
        self.assertEqual(len(AllFieldsTestCase.TRIALS),
                         len(fields._field_configs))

        for key, generator in AllFieldsTestCase.TRIALS.items():
            db_objs = generator()

            fields_dict = fields._field_configs[key]

            for db_obj in db_objs:
                for field_config in fields_dict.values():
                    context = Context()
                    context.request = AllFieldsTestCase.MockRequest()

                    field_config.accessor(context, db_obj)


class FieldFnsTestCase(TestCase):
    def test_feedentry_isRead(self):
        context = Context()

        user = models.User.objects.create(
            email='test_fields@test.com')

        class MockRequest:
            def __init__(self):
                self.user = user

        context.request = MockRequest()

        feed = models.Feed.objects.create(
            feed_url='http://example.com/rss.xml',
            title='Sample Feed',
            home_url='http://example.com',
            published_at=datetime.datetime.utcnow(),
            updated_at=None,
            db_updated_at=None)

        feed_entry1 = models.FeedEntry.objects.create(
            feed=feed,
            url='http://example.com/entry1.html',
            content='<b>Some HTML Content</b>',
            author_name='John Doe')
        feed_entry2 = models.FeedEntry.objects.create(
            feed=feed,
            url='http://example.com/entry2.html',
            content='<b>Some HTML Content</b>',
            author_name='John Doe')

        models.ReadFeedEntryUserMapping.objects.create(feed_entry=feed_entry2, user=user)

        self.assertIsNone(fields._feedentry_readAt(context, feed_entry1))
        self.assertIsNotNone(fields._feedentry_readAt(context, feed_entry2))
