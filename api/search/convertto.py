import datetime
import re
import uuid

from dateutil.relativedelta import relativedelta
from django.utils import timezone

_min_dt = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
_max_dt = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)


class CustomConvertTo:
    @staticmethod
    def convertto(search_obj: str):
        raise RuntimeError("Abstract Method")


class Bool(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        return search_obj.lower() == "true"


class Int(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        return int(search_obj)


class IntList(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        if search_obj.strip() == "":
            return []

        return [int(part) for part in search_obj.split(",")]


class IntRange(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        parts = search_obj.split("|")
        return (int(parts[0]), int(parts[1]))


class FloatRange(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        parts = search_obj.split("|")
        return (float(parts[0]), float(parts[1]))


class DateTime(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        return datetime.datetime.fromisoformat(search_obj)


class DateTimeRange(CustomConvertTo):
    @staticmethod
    def _to_datetime(part: str):
        return datetime.datetime.fromisoformat(part)

    @staticmethod
    def convertto(search_obj: str):
        parts = search_obj.split("|")

        start_datetime = DateTimeRange._to_datetime(parts[0]) if parts[0] else _min_dt
        end_datetime = DateTimeRange._to_datetime(parts[1]) if parts[1] else _max_dt
        return start_datetime, end_datetime


class Uuid(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        return uuid.UUID(search_obj)


class UuidList(CustomConvertTo):
    @staticmethod
    def convertto(search_obj: str):
        return [uuid.UUID(uuid_str) for uuid_str in search_obj.split(",")]


_DATE_DELTA_RANGE_OLDER_THAN_REGEX = re.compile(r"^older_than:(\d+)([yMwdhms])$")
_DATE_DELTA_RANGE_EARLIER_THAN_REGEX = re.compile(r"^earlier_than:(\d+)([yMwdhms])$")


class DateTimeDeltaRange(CustomConvertTo):
    @staticmethod
    def _diff(type_: str, number: int):
        if type_ == "y":
            return relativedelta(years=-number)
        elif type_ == "M":
            return relativedelta(months=-number)
        elif type_ == "w":
            return relativedelta(weeks=-number)
        elif type_ == "d":
            return relativedelta(days=-number)
        elif type_ == "h":
            return relativedelta(hours=-number)
        elif type_ == "m":
            return relativedelta(minutes=-number)
        elif type_ == "s":
            return relativedelta(seconds=-number)

        raise RuntimeError("unknown type_")  # pragma: no cover

    @staticmethod
    def convertto(search_obj: str, now: datetime.datetime | None = None):
        now = now or timezone.now()

        older_than_match = _DATE_DELTA_RANGE_OLDER_THAN_REGEX.search(search_obj)
        if older_than_match:
            number = int(older_than_match.group(1))
            type_ = older_than_match.group(2)

            return _min_dt, now + DateTimeDeltaRange._diff(type_, number)
        else:
            earlier_than_match = _DATE_DELTA_RANGE_EARLIER_THAN_REGEX.search(search_obj)
            if earlier_than_match:
                number = int(earlier_than_match.group(1))
                type_ = earlier_than_match.group(2)

                return (
                    now + DateTimeDeltaRange._diff(type_, number),
                    _max_dt,
                )
            else:
                raise ValueError("date delta malformed")
