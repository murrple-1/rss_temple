import logging
import uuid
from typing import Any, Callable, ClassVar
from unittest.mock import Mock

from django.http import HttpRequest
from django.test import TestCase
from django.utils import timezone

from api import fields
from api.models import (
    Feed,
    FeedEntry,
    ReadFeedEntryUserMapping,
    SubscribedFeedUserMapping,
    User,
    UserCategory,
)


class _ObjectConfig:
    def __init__(
        self,
        object_name,
        all_count,
        default_count,
        good_field_name,
        bad_field_name="bad_field_name",
    ):
        self.object_name = object_name
        self.all_count = all_count
        self.default_count = default_count
        self.good_field_name = good_field_name
        self.bad_field_name = bad_field_name


_object_configs = [
    _ObjectConfig("feed", 12, 1, "uuid"),
    _ObjectConfig("feedentry", 14, 1, "uuid"),
    _ObjectConfig("usercategory", 3, 2, "uuid"),
]


class FieldsTestCase(TestCase):
    def test_default_field_maps(self):
        for oc in _object_configs:
            default_field_maps = fields.get_default_field_maps(oc.object_name)

            self.assertEqual(len(default_field_maps), oc.default_count)

            for field_map in default_field_maps:
                self.assertIn("field_name", field_map)
                self.assertIs(type(field_map["field_name"]), str)
                self.assertIn("accessor", field_map)
                self.assertTrue(callable(field_map["accessor"]))

    def test_all_field_maps(self):
        for oc in _object_configs:
            all_field_maps = fields.get_all_field_maps(oc.object_name)

            self.assertEqual(len(all_field_maps), oc.all_count)

            for field_map in all_field_maps:
                self.assertIn("field_name", field_map)
                self.assertIs(type(field_map["field_name"]), str)
                self.assertIn("accessor", field_map)
                self.assertTrue(callable(field_map["accessor"]))

    def test_fieldconfig(self):
        fc = fields._FieldConfig(lambda request, db_obj: "test", True)

        self.assertEqual(fc.accessor(Mock(HttpRequest), object()), "test")
        self.assertTrue(fc.default)

    def test_to_field_map(self):
        for oc in _object_configs:
            field_map = fields.to_field_map(oc.object_name, oc.good_field_name)

            assert field_map is not None

            self.assertEqual(field_map["field_name"], oc.good_field_name)

            class TestObject:
                def __init__(self):
                    self.uuid = uuid.uuid4()

            field_map["accessor"](Mock(HttpRequest), TestObject())

            field_map = fields.to_field_map(oc.object_name, oc.bad_field_name)
            self.assertIsNone(field_map)


class AllFieldsTestCase(TestCase):
    old_logger_level: ClassVar[int]
    TRIALS: ClassVar[dict[str, Callable[[], list[Any]]]]
    user: ClassVar[User]
    user_category: ClassVar[UserCategory]
    feed_with_category: ClassVar[Feed]
    feed_without_category: ClassVar[Feed]
    feed_entry: ClassVar[FeedEntry]

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

    class MockRequest(Mock):
        def __init__(self):
            super().__init__(HttpRequest)
            self.user = AllFieldsTestCase.user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)

        cls.TRIALS = {
            "usercategory": AllFieldsTestCase.generate_usercategories,
            "feed": AllFieldsTestCase.generate_feeds,
            "feedentry": AllFieldsTestCase.generate_feedentries,
        }

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_logger_level)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test_fields@test.com", None)

        cls.user_category = UserCategory.objects.create(
            user=cls.user, text="Test Category"
        )

        cls.feed_with_category = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        cls.feed_without_category = Feed.objects.create(
            feed_url="http://example2.com/rss.xml",
            title="Sample Feed 2",
            home_url="http://example2.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        cls.feed_entry = FeedEntry.objects.create(
            feed=cls.feed_with_category,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        SubscribedFeedUserMapping.objects.create(
            feed=cls.feed_with_category,
            user=cls.user,
            custom_feed_title="Custom Title 1",
        )

        SubscribedFeedUserMapping.objects.create(
            feed=cls.feed_without_category, user=cls.user, custom_feed_title=None
        )

        cls.user_category.feeds.add(cls.feed_with_category)

    def test_run(self):
        self.assertEqual(len(AllFieldsTestCase.TRIALS), len(fields._field_configs))

        for key, generator in AllFieldsTestCase.TRIALS.items():
            with self.subTest(key=key):
                db_objs = generator()

                fields_dict = fields._field_configs[key]

                for db_obj in db_objs:
                    for field_config in fields_dict.values():
                        field_config.accessor(AllFieldsTestCase.MockRequest(), db_obj)


class FieldFnsTestCase(TestCase):
    def test_feedentry_isRead(self):
        user = User.objects.create_user("test_fields@test.com", None)

        class MockRequest(Mock):
            def __init__(self):
                super().__init__(HttpRequest)
                self.user = user

        request = MockRequest()

        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        feed_entry1 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        feed_entry2 = FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        ReadFeedEntryUserMapping.objects.create(feed_entry=feed_entry2, user=user)

        self.assertIsNone(fields._feedentry_readAt(request, feed_entry1))
        self.assertIsNotNone(fields._feedentry_readAt(request, feed_entry2))
