import datetime
import uuid

from django.test import TestCase

from api.search.convertto import (
    Bool,
    DateTime,
    DateTimeDeltaRange,
    DateTimeRange,
    FloatRange,
    Int,
    IntList,
    IntRange,
    Uuid,
    UuidList,
)


class ConvertToTestCase(TestCase):
    def test_bool(self):
        self.assertTrue(Bool.convertto("true"))
        self.assertFalse(Bool.convertto("false"))
        self.assertFalse(Bool.convertto(""))
        self.assertTrue(Bool.convertto("True"))
        self.assertTrue(Bool.convertto("TRUE"))

    def test_int(self):
        self.assertEqual(Int.convertto("1"), 1)
        self.assertEqual(Int.convertto("0"), 0)
        self.assertEqual(Int.convertto("-1"), -1)
        with self.assertRaises(ValueError):
            Int.convertto("")

        with self.assertRaises(ValueError):
            Int.convertto("text")

    def test_int_list(self):
        self.assertEqual(IntList.convertto(""), [])
        self.assertEqual(IntList.convertto("1"), [1])
        self.assertEqual(IntList.convertto("1,2"), [1, 2])
        self.assertEqual(IntList.convertto("-1"), [-1])
        self.assertEqual(IntList.convertto("-1,-2"), [-1, -2])

        with self.assertRaises(ValueError):
            IntList.convertto("test")

    def test_int_range(self):
        self.assertEqual(IntRange.convertto("1|5"), (1, 5))
        self.assertEqual(IntRange.convertto("-1|-5"), (-1, -5))

        with self.assertRaises(IndexError):
            IntRange.convertto("1")

        with self.assertRaises(ValueError):
            IntRange.convertto("text|text")

    def test_float_range(self):
        range_ = FloatRange.convertto("1.0|2.0")

        self.assertAlmostEqual(range_[0], 1.0)
        self.assertAlmostEqual(range_[1], 2.0)

        range_ = FloatRange.convertto("-1.0|-2.0")

        self.assertAlmostEqual(range_[0], -1.0)
        self.assertAlmostEqual(range_[1], -2.0)

        range_ = FloatRange.convertto("1|2")

        self.assertAlmostEqual(range_[0], 1.0)
        self.assertAlmostEqual(range_[1], 2.0)

        with self.assertRaises(IndexError):
            FloatRange.convertto("1.0")

        with self.assertRaises(ValueError):
            FloatRange.convertto("text|text")

    def test_uuid(self):
        uuid_str = "d494d009-5d07-4fc6-877b-e9ce5b84b44b"
        uuid_ = uuid.UUID(uuid_str)

        self.assertEqual(Uuid.convertto(uuid_str), uuid_)

        with self.assertRaises(ValueError):
            Uuid.convertto("")

    def test_uuid_list(self):
        uuid_str1 = "d494d009-5d07-4fc6-877b-e9ce5b84b44b"
        uuid_1 = uuid.UUID(uuid_str1)

        uuid_str2 = "93782415-c3d9-4ec0-b6c2-435d8aab34f3"
        uuid_2 = uuid.UUID(uuid_str2)

        self.assertEqual(UuidList.convertto(uuid_str1), [uuid_1])
        self.assertEqual(
            UuidList.convertto(f"{uuid_str1},{uuid_str2}"), [uuid_1, uuid_2]
        )

        with self.assertRaises(ValueError):
            UuidList.convertto("test")

    def test_datetime(self):
        self.assertEqual(
            DateTime.convertto("2000-01-01 00:00:00"),
            datetime.datetime(2000, 1, 1, 0, 0, 0),
        )

        with self.assertRaises(ValueError):
            DateTime.convertto("bad text")

    def test_datetime_range(self):
        range_ = DateTimeRange.convertto("2000-01-01 00:00:00|2000-01-02 23:59:59")

        self.assertEqual(range_[0], datetime.datetime(2000, 1, 1, 0, 0, 0))
        self.assertEqual(range_[1], datetime.datetime(2000, 1, 2, 23, 59, 59))

        range_ = DateTimeRange.convertto("2000-01-01 00:00:00|")

        self.assertEqual(range_[0], datetime.datetime(2000, 1, 1, 0, 0, 0))
        self.assertEqual(
            range_[1], datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
        )

        range_ = DateTimeRange.convertto("|2000-01-02 23:59:59")

        self.assertEqual(
            range_[0], datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        )
        self.assertEqual(range_[1], datetime.datetime(2000, 1, 2, 23, 59, 59))

        range_ = DateTimeRange.convertto("|")

        self.assertEqual(
            range_[0], datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        )
        self.assertEqual(
            range_[1], datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
        )

        with self.assertRaises(ValueError):
            DateTimeRange.convertto("text|text")

        with self.assertRaises(IndexError):
            DateTimeRange.convertto("2000-01-01 00:00:00")

    def test_datetime_delta_range_older_than(self):
        now = datetime.datetime(2000, 11, 11, 0, 0, 0, 0)

        older_than_10y_end = datetime.datetime(1990, 11, 11, 0, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("older_than:10y", now=now),
            (
                datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                older_than_10y_end,
            ),
        )

        older_than_10M_end = datetime.datetime(2000, 1, 11, 0, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("older_than:10M", now=now),
            (
                datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                older_than_10M_end,
            ),
        )

        older_than_1w_end = datetime.datetime(2000, 11, 4, 0, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("older_than:1w", now=now),
            (
                datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                older_than_1w_end,
            ),
        )

        older_than_10d_end = datetime.datetime(2000, 11, 1, 0, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("older_than:10d", now=now),
            (
                datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                older_than_10d_end,
            ),
        )

        older_than_10h_end = datetime.datetime(2000, 11, 10, 14, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("older_than:10h", now=now),
            (
                datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                older_than_10h_end,
            ),
        )

        older_than_10m_end = datetime.datetime(2000, 11, 10, 23, 50, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("older_than:10m", now=now),
            (
                datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                older_than_10m_end,
            ),
        )

        older_than_10s_end = datetime.datetime(2000, 11, 10, 23, 59, 50, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("older_than:10s", now=now),
            (
                datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                older_than_10s_end,
            ),
        )

    def test_datetime_delta_range_earlier_than(self):
        now = datetime.datetime(2000, 11, 11, 0, 0, 0, 0)

        earlier_than_10y_end = datetime.datetime(1990, 11, 11, 0, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("earlier_than:10y", now=now),
            (
                earlier_than_10y_end,
                datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
            ),
        )

        earlier_than_10M_end = datetime.datetime(2000, 1, 11, 0, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("earlier_than:10M", now=now),
            (
                earlier_than_10M_end,
                datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
            ),
        )

        earlier_than_1w_end = datetime.datetime(2000, 11, 4, 0, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("earlier_than:1w", now=now),
            (
                earlier_than_1w_end,
                datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
            ),
        )

        earlier_than_10d_end = datetime.datetime(2000, 11, 1, 0, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("earlier_than:10d", now=now),
            (
                earlier_than_10d_end,
                datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
            ),
        )

        earlier_than_10h_end = datetime.datetime(2000, 11, 10, 14, 0, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("earlier_than:10h", now=now),
            (
                earlier_than_10h_end,
                datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
            ),
        )

        earlier_than_10m_end = datetime.datetime(2000, 11, 10, 23, 50, 0, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("earlier_than:10m", now=now),
            (
                earlier_than_10m_end,
                datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
            ),
        )

        earlier_than_10s_end = datetime.datetime(2000, 11, 10, 23, 59, 50, 0)

        self.assertEqual(
            DateTimeDeltaRange.convertto("earlier_than:10s", now=now),
            (
                earlier_than_10s_end,
                datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
            ),
        )

    def test_date_delta_range_error(self):
        with self.assertRaises(ValueError):
            DateTimeDeltaRange.convertto("test")
