import uuid
import datetime

from django.test import TestCase

from api.search.convertto import (
    CustomConvertTo,
    Bool,
    Int,
    IntList,
    IntRange,
    FloatRange,
    Uuid,
    UuidList,
    Date,
    DateRange,
    DateDeltaRange,
)


class ConvertToTestCase(TestCase):
    def test_customconvertto(self):
        with self.assertRaises(RuntimeError):
            CustomConvertTo.convertto('')

    def test_bool(self):
        self.assertTrue(Bool.convertto('true'))
        self.assertFalse(Bool.convertto('false'))
        self.assertFalse(Bool.convertto(''))
        self.assertTrue(Bool.convertto('True'))
        self.assertTrue(Bool.convertto('TRUE'))

    def test_int(self):
        self.assertEqual(Int.convertto('1'), 1)
        self.assertEqual(Int.convertto('0'), 0)
        self.assertEqual(Int.convertto('-1'), -1)
        with self.assertRaises(ValueError):
            Int.convertto('')

        with self.assertRaises(ValueError):
            Int.convertto('text')

    def test_int_list(self):
        self.assertEqual(IntList.convertto(''), [])
        self.assertEqual(IntList.convertto('1'), [1])
        self.assertEqual(IntList.convertto('1,2'), [1, 2])
        self.assertEqual(IntList.convertto('-1'), [-1])
        self.assertEqual(IntList.convertto('-1,-2'), [-1, -2])

        with self.assertRaises(ValueError):
            IntList.convertto('test')

    def test_int_range(self):
        self.assertEqual(IntRange.convertto('1|5'), (1, 5))
        self.assertEqual(IntRange.convertto('-1|-5'), (-1, -5))

        with self.assertRaises(IndexError):
            IntRange.convertto('1')

        with self.assertRaises(ValueError):
            IntRange.convertto('text|text')

    def test_float_range(self):
        range_ = FloatRange.convertto('1.0|2.0')

        self.assertAlmostEqual(range_[0], 1.0)
        self.assertAlmostEqual(range_[1], 2.0)

        range_ = FloatRange.convertto('-1.0|-2.0')

        self.assertAlmostEqual(range_[0], -1.0)
        self.assertAlmostEqual(range_[1], -2.0)

        range_ = FloatRange.convertto('1|2')

        self.assertAlmostEqual(range_[0], 1.0)
        self.assertAlmostEqual(range_[1], 2.0)

        with self.assertRaises(IndexError):
            FloatRange.convertto('1.0')

        with self.assertRaises(ValueError):
            FloatRange.convertto('text|text')

    def test_uuid(self):
        uuid_str = 'd494d009-5d07-4fc6-877b-e9ce5b84b44b'
        uuid_ = uuid.UUID(uuid_str)

        self.assertEqual(Uuid.convertto(uuid_str), uuid_)

        with self.assertRaises(ValueError):
            Uuid.convertto('')

    def test_uuid_list(self):
        uuid_str1 = 'd494d009-5d07-4fc6-877b-e9ce5b84b44b'
        uuid_1 = uuid.UUID(uuid_str1)

        uuid_str2 = '93782415-c3d9-4ec0-b6c2-435d8aab34f3'
        uuid_2 = uuid.UUID(uuid_str2)

        self.assertEqual(UuidList.convertto(uuid_str1), [uuid_1])
        self.assertEqual(UuidList.convertto(
            f'{uuid_str1},{uuid_str2}'), [uuid_1, uuid_2])

        with self.assertRaises(ValueError):
            UuidList.convertto('test')

    def test_date(self):
        self.assertEqual(Date.convertto('2000-01-01'),
                         datetime.date(2000, 1, 1))

        with self.assertRaises(ValueError):
            Date.convertto('bad text')

    def test_date_range(self):
        range_ = DateRange.convertto('2000-01-01|2000-01-02')

        self.assertEqual(range_[0], datetime.datetime(2000, 1, 1, 0, 0, 0))
        self.assertEqual(range_[1], datetime.datetime(2000, 1, 2, 23, 59, 59))

        range_ = DateRange.convertto('2000-01-01|')

        self.assertEqual(range_[0], datetime.datetime(2000, 1, 1, 0, 0, 0))
        self.assertEqual(range_[1], datetime.datetime.max)

        range_ = DateRange.convertto('|2000-01-02')

        self.assertEqual(range_[0], datetime.datetime.min)
        self.assertEqual(range_[1], datetime.datetime(2000, 1, 2, 23, 59, 59))

        range_ = DateRange.convertto('|')

        self.assertEqual(range_[0], datetime.datetime.min)
        self.assertEqual(range_[1], datetime.datetime.max)

        with self.assertRaises(ValueError):
            DateRange.convertto('text|text')

        with self.assertRaises(IndexError):
            DateRange.convertto('2000-01-01')

    def test_date_delta_range_yesterday(self):
        now = datetime.datetime(2000, 1, 2, 0, 0, 0, 0)

        yesterday_start = datetime.datetime(2000, 1, 1, 0, 0, 0, 0)
        yesterday_end = datetime.datetime(2000, 1, 1, 23, 59, 59, 999999)

        self.assertEqual(DateDeltaRange.convertto(
            'yesterday', now=now), (yesterday_start, yesterday_end))

    def test_date_delta_range_last_week(self):
        now = datetime.datetime(2000, 1, 15, 0, 0, 0, 0)
        last_week_start = datetime.datetime(2000, 1, 3, 0, 0, 0, 0)
        last_week_end = datetime.datetime(2000, 1, 9, 23, 59, 59, 999999)

        self.assertEqual(DateDeltaRange.convertto(
            'last_week', now=now), (last_week_start, last_week_end))

    def test_date_delta_range_last_month(self):
        now = datetime.datetime(2000, 2, 1, 0, 0, 0, 0)
        last_month_start = datetime.datetime(2000, 1, 1)
        last_month_end = datetime.datetime(2000, 1, 31, 23, 59, 59, 999999)

        self.assertEqual(DateDeltaRange.convertto(
            'last_month', now=now), (last_month_start, last_month_end))

    def test_date_delta_range_last_year(self):
        now = datetime.datetime(2000, 1, 1, 0, 0, 0, 0)
        last_year_start = datetime.datetime(1999, 1, 1, 0, 0, 0, 0)
        last_year_end = datetime.datetime(1999, 12, 31, 23, 59, 59, 999999)

        self.assertEqual(DateDeltaRange.convertto(
            'last_year', now=now), (last_year_start, last_year_end))

    def test_date_delta_range_year_to_date(self):
        now = datetime.datetime(2000, 6, 15, 7, 0, 0, 0)
        year_to_date_start = datetime.datetime(2000, 1, 1, 0, 0, 0, 0)
        year_to_date_end = now

        self.assertEqual(DateDeltaRange.convertto(
            'year_to_date', now=now), (year_to_date_start, year_to_date_end))

    def test_date_delta_range_older_than(self):
        now = datetime.datetime(2000, 11, 11, 0, 0, 0, 0)

        older_than_10d_end = datetime.datetime(2000, 11, 1, 0, 0, 0, 0)

        self.assertEqual(DateDeltaRange.convertto(
            'older_than:10d', now=now), (datetime.datetime.min, older_than_10d_end))

        older_than_10m_end = datetime.datetime(2000, 1, 11, 0, 0, 0, 0)

        self.assertEqual(DateDeltaRange.convertto(
            'older_than:10m', now=now), (datetime.datetime.min, older_than_10m_end))

        older_than_10y_end = datetime.datetime(1990, 11, 11, 0, 0, 0, 0)

        self.assertEqual(DateDeltaRange.convertto(
            'older_than:10y', now=now), (datetime.datetime.min, older_than_10y_end))

    def test_date_delta_range_earlier_than(self):
        now = datetime.datetime(2000, 11, 11, 11, 0, 0, 0)

        earlier_than_10h_start = datetime.datetime(2000, 11, 11, 1, 0, 0, 0)

        self.assertEqual(DateDeltaRange.convertto(
            'earlier_than:10h', now=now), (earlier_than_10h_start, datetime.datetime.max))

        earlier_than_10d_start = datetime.datetime(2000, 11, 1, 11, 0, 0, 0)

        self.assertEqual(DateDeltaRange.convertto(
            'earlier_than:10d', now=now), (earlier_than_10d_start, datetime.datetime.max))

        earlier_than_10m_start = datetime.datetime(2000, 1, 11, 11, 0, 0, 0)

        self.assertEqual(DateDeltaRange.convertto(
            'earlier_than:10m', now=now), (earlier_than_10m_start, datetime.datetime.max))

        earlier_than_10y_start = datetime.datetime(1990, 11, 11, 11, 0, 0, 0)

        self.assertEqual(DateDeltaRange.convertto(
            'earlier_than:10y', now=now), (earlier_than_10y_start, datetime.datetime.max))

    def test_date_delta_range_error(self):
        with self.assertRaises(ValueError):
            DateDeltaRange.convertto('test')
