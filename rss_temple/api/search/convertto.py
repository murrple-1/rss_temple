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


class DateTime(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        return datetime.datetime.strptime(search_obj, '%Y-%m-%d %H:%M:%S')


class DateTimeRange(CustomConvertTo):
    @staticmethod
    def _to_datetime(part):
        return datetime.datetime.strptime(part, '%Y-%m-%d %H:%M:%S')

    @staticmethod
    def convertto(search_obj):
        parts = search_obj.split('|')

        start_datetime = DateTimeRange._to_datetime(
            parts[0]) if parts[0] else datetime.datetime.min
        end_datetime = DateTimeRange._to_datetime(
            parts[1]) if parts[1] else datetime.datetime.max
        return start_datetime, end_datetime


class Uuid(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        return uuid.UUID(search_obj)


class UuidList(CustomConvertTo):
    @staticmethod
    def convertto(search_obj):
        return [uuid.UUID(uuid_str) for uuid_str in search_obj.split(',')]


_DATE_DELTA_RANGE_OLDER_THAN_REGEX = re.compile(
    r'^older_than:(\d+)([yMwdhms])$')
_DATE_DELTA_RANGE_EARLIER_THAN_REGEX = re.compile(
    r'^earlier_than:(\d+)([yMwdhms])$')


class DateTimeDeltaRange(CustomConvertTo):
    @staticmethod
    def _diff(type_, number):
        if type_ == 'y':
            return relativedelta(years=-number)
        elif type_ == 'M':
            return relativedelta(months=-number)
        elif type_ == 'w':
            return relativedelta(weeks=-number)
        elif type_ == 'd':
            return relativedelta(days=-number)
        elif type_ == 'h':
            return relativedelta(hours=-number)
        elif type_ == 'm':
            return relativedelta(minutes=-number)
        elif type_ == 's':
            return relativedelta(seconds=-number)

        raise RuntimeError('unknown type_')  # pragma: no cover

    @staticmethod
    def convertto(search_obj, now=None):
        now = now or datetime.datetime.utcnow()

        older_than_match = _DATE_DELTA_RANGE_OLDER_THAN_REGEX.search(
            search_obj)
        if older_than_match:
            number = int(older_than_match.group(1))
            type_ = older_than_match.group(2)

            return datetime.datetime.min, now + DateTimeDeltaRange._diff(type_, number)
        else:
            earlier_than_match = _DATE_DELTA_RANGE_EARLIER_THAN_REGEX.search(
                search_obj)
            if earlier_than_match:
                number = int(earlier_than_match.group(1))
                type_ = earlier_than_match.group(2)

                return now + DateTimeDeltaRange._diff(type_, number), datetime.datetime.max
            else:
                raise ValueError('date delta malformed')
