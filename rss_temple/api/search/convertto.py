import datetime
import uuid
import re
import calendar

from dateutil.relativedelta import relativedelta


class CustomConvertTo:
    @staticmethod
    def convertto(search_obj):
        raise RuntimeError('Abstract Method')


class Bool(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        return search_obj.lower() == 'true'


class Int(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        return int(search_obj)


class IntList(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        if search_obj.strip() == '':
            return []

        return [int(part) for part in search_obj.split(',')]


class IntRange(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        parts = search_obj.split('|')
        return (int(parts[0]), int(parts[1]))


class FloatRange(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        parts = search_obj.split('|')
        return (float(parts[0]), float(parts[1]))


class Date(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        return datetime.datetime.strptime(search_obj, '%Y-%m-%d').date()


class DateRange(CustomConvertTo):
    @staticmethod
    def _to_datetime(part):
        return datetime.datetime.strptime(part, '%Y-%m-%d %H:%M:%S')

    @staticmethod
    def convertto(search_obj):
        parts = search_obj.split('|')

        start_datetime = DateRange._to_datetime('{0} 00:00:00'.format(
            parts[0])) if parts[0] else datetime.datetime.min
        end_datetime = DateRange._to_datetime('{0} 23:59:59'.format(
            parts[1])) if parts[1] else datetime.datetime.max
        return start_datetime, end_datetime


class Uuid(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        return uuid.UUID(search_obj)


class UuidList(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        return [uuid.UUID(uuid_str) for uuid_str in search_obj.split('|')]


_DATE_DELTA_RANGE_OLDER_THAN_REGEX = re.compile(r'^older_than:(\d+)([dmy])$')
_DATE_DELTA_RANGE_EARLIER_THAN_REGEX = re.compile(
    r'^earlier_than:(\d+)([hdmy])$')


class DateDeltaRange(CustomConvertTo):
    @staticmethod
    def convertto(search_obj, now=None):
        now = now or datetime.datetime.utcnow()

        if search_obj == 'yesterday':
            yesterday = (now + relativedelta(days=-1))
            start_day = yesterday.replace(
                hour=0, minute=0, second=0, microsecond=0)
            end_day = yesterday.replace(
                hour=23, minute=59, second=59, microsecond=999999)

            return start_day, end_day
        elif search_obj == 'last_week':
            last_week = now + relativedelta(weeks=-1)
            start_day = (
                last_week +
                relativedelta(
                    days=-
                    now.weekday())).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0)
            end_day = (
                last_week +
                relativedelta(
                    days=(
                        6 -
                        now.weekday()))).replace(
                hour=23,
                minute=59,
                second=59,
                microsecond=999999)

            return start_day, end_day
        elif search_obj == 'last_month':
            last_month = now + relativedelta(months=-1)
            start_day = last_month.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0)
            end_day = last_month.replace(
                day=(
                    calendar.monthrange(
                        last_month.year,
                        last_month.month))[1],
                hour=23,
                minute=59,
                second=59,
                microsecond=999999)

            return start_day, end_day
        elif search_obj == 'last_year':
            last_year = now + relativedelta(years=-1)
            start_day = last_year.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_day = last_year.replace(
                month=12,
                day=31,
                hour=23,
                minute=59,
                second=59,
                microsecond=999999)

            return start_day, end_day
        elif search_obj == 'year_to_date':
            start_day = now.replace(
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0)

            return start_day, now
        else:
            older_than_match = _DATE_DELTA_RANGE_OLDER_THAN_REGEX.search(
                search_obj)
            if older_than_match:
                number = int(older_than_match.group(1))
                _type = older_than_match.group(2)

                epoch = None
                if _type == 'd':
                    epoch = now + relativedelta(days=-number)
                elif _type == 'm':
                    epoch = now + relativedelta(months=-number)
                elif _type == 'y':
                    epoch = now + relativedelta(years=-number)

                return datetime.datetime.min, epoch
            else:
                earlier_than_match = _DATE_DELTA_RANGE_EARLIER_THAN_REGEX.search(
                    search_obj)
                if earlier_than_match:
                    number = int(earlier_than_match.group(1))
                    _type = earlier_than_match.group(2)

                    epoch = None
                    if _type == 'h':
                        epoch = now + relativedelta(hours=-number)
                    elif _type == 'd':
                        epoch = now + relativedelta(days=-number)
                    elif _type == 'm':
                        epoch = now + relativedelta(months=-number)
                    elif _type == 'y':
                        epoch = now + relativedelta(years=-number)

                    return epoch, datetime.datetime.max
                else:
                    raise ValueError('date delta malformed')
