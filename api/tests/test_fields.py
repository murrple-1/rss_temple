import datetime
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
    _ObjectConfig("feed", 13, 1, "uuid"),
    _ObjectConfig("feedentry", 20, 1, "uuid"),
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
        fc = fields._FieldConfig(lambda request, db_obj, queryset: "test", True)

        db_obj = object()
        queryset = [db_obj]
        self.assertEqual(fc.accessor(Mock(HttpRequest), db_obj, queryset), "test")
        self.assertTrue(fc.default)

    def test_to_field_map(self):
        for oc in _object_configs:
            field_map = fields.to_field_map(oc.object_name, oc.good_field_name)

            assert field_map is not None

            self.assertEqual(field_map["field_name"], oc.good_field_name)

            class TestObject:
                def __init__(self):
                    self.uuid = uuid.uuid4()

            db_obj = TestObject()
            queryset = [db_obj]

            field_map["accessor"](Mock(HttpRequest), db_obj, queryset)

            field_map = fields.to_field_map(oc.object_name, oc.bad_field_name)
            self.assertIsNone(field_map)

    def test_generate_return_object(self):
        field_maps: list[fields.FieldMap] = [
            {
                "field_name": "uuid",
                "accessor": lambda request, db_obj, queryset: db_obj.uuid,
            }
        ]

        db_obj = Mock()
        db_obj.uuid = "test string"

        queryset = [db_obj]

        self.assertEqual(
            fields.generate_return_object(
                field_maps, db_obj, Mock(HttpRequest), queryset
            ),
            {
                "uuid": "test string",
            },
        )


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
            feed.with_subscription_data()

        return feeds

    @classmethod
    def generate_feedentries(cls):
        feed_entries = [cls.feed_entry]

        for feed_entry in feed_entries:
            feed_entry.with_user_data()

        return feed_entries

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
                        self.assertEqual(
                            field_config.accessor(
                                AllFieldsTestCase.MockRequest(), db_obj, db_objs
                            ),
                            field_config.accessor(
                                AllFieldsTestCase.MockRequest(), db_obj, None
                            ),
                        )


class FieldFnsTestCase(TestCase):
    user: ClassVar[User]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test_fields@test.com", None)

    class MockRequest(Mock):
        def __init__(self):
            super().__init__(HttpRequest)
            self.user = FieldFnsTestCase.user

    def test__usercategory_feedUuids(self):
        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        user_category = UserCategory.objects.create(
            user=FieldFnsTestCase.user,
            text="Test Category",
        )
        user_category.feeds.add(feed)

        for queryset in [None, UserCategory.objects.all()]:
            with self.subTest(queryset_type=type(queryset)):
                feed_uuids = fields._usercategory_feedUuids(
                    FieldFnsTestCase.MockRequest(), user_category, queryset
                )
                self.assertIsInstance(feed_uuids, list)
                self.assertEqual(len(feed_uuids), 1)

    def test__feed_userCategoryUuids(self):
        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        user_category = UserCategory.objects.create(
            user=FieldFnsTestCase.user,
            text="Test Category",
        )
        user_category.feeds.add(feed)

        for queryset in [None, Feed.objects.all()]:
            with self.subTest(queryset_type=type(queryset)):
                user_category_uuids = fields._feed_userCategoryUuids(
                    FieldFnsTestCase.MockRequest(), feed, queryset
                )
                self.assertIsInstance(user_category_uuids, list)
                self.assertEqual(len(user_category_uuids), 1)

    def test_feed_readCount(self):
        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        FieldFnsTestCase.user.read_feed_entries.add(feed.feed_entries.first())

        for queryset in [None, Feed.objects.all()]:
            with self.subTest(queryset_type=type(queryset)):
                self.assertEqual(
                    fields._feed_readCount(
                        FieldFnsTestCase.MockRequest(), feed, queryset
                    ),
                    1,
                )

    def test_feed_unreadCount(self):
        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=timezone.now(),
            updated_at=None,
            db_updated_at=None,
        )

        FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry1.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )
        FeedEntry.objects.create(
            feed=feed,
            url="http://example.com/entry2.html",
            content="<b>Some HTML Content</b>",
            author_name="John Doe",
        )

        FieldFnsTestCase.user.read_feed_entries.add(feed.feed_entries.first())

        for queryset in [None, Feed.objects.all()]:
            with self.subTest(queryset_type=type(queryset)):
                self.assertEqual(
                    fields._feed_unreadCount(
                        FieldFnsTestCase.MockRequest(), feed, queryset
                    ),
                    1,
                )

    def test_feed_isDead(self):
        with self.settings(FEED_IS_DEAD_MAX_INTERVAL=datetime.timedelta(days=28.0)):
            feed = Feed.objects.create(
                feed_url="http://example.com/rss.xml",
                title="Sample Feed",
                home_url="http://example.com",
                published_at=timezone.now(),
                updated_at=None,
            )

            for queryset in [None, Feed.objects.all()]:
                with self.subTest(queryset_type=type(queryset)):
                    feed.db_updated_at = None
                    feed.save(update_fields=("db_updated_at",))

                    self.assertFalse(
                        fields._feed_isDead(
                            FieldFnsTestCase.MockRequest(), feed, queryset
                        )
                    )

                    feed.db_updated_at = timezone.now()
                    feed.save(update_fields=("db_updated_at",))

                    self.assertFalse(
                        fields._feed_isDead(
                            FieldFnsTestCase.MockRequest(), feed, queryset
                        )
                    )

                    feed.db_updated_at = timezone.now() + datetime.timedelta(
                        days=-(28.0 * 2.0)
                    )
                    feed.save(update_fields=("db_updated_at",))

                    self.assertTrue(
                        fields._feed_isDead(
                            FieldFnsTestCase.MockRequest(), feed, queryset
                        )
                    )

    def test_feedentry_readAt(self):
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

        ReadFeedEntryUserMapping.objects.create(
            feed_entry=feed_entry2, user=FieldFnsTestCase.user
        )

        for queryset in [None, FeedEntry.objects.all()]:
            with self.subTest(queryset_type=type(queryset)):
                self.assertIsNone(
                    fields._feedentry_readAt(
                        FieldFnsTestCase.MockRequest(), feed_entry1, queryset
                    )
                )
                self.assertIsNotNone(
                    fields._feedentry_readAt(
                        FieldFnsTestCase.MockRequest(), feed_entry2, queryset
                    )
                )
