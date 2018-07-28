from django.conf import settings


class Context:
    def __init__(self):
        self.datetime_format = getattr(
            settings, 'DEFAULT_DATETIME_FORMAT', '%Y-%m-%d %H:%M:%S')
        self.date_format = getattr(settings, 'DEFAULT_DATE_FORMAT', '%Y-%m-%d')
        self.time_format = getattr(settings, 'DEFAULT_TIME_FORMAT', '%H:%M:%S')

    def parse_query_dict(self, query_dict):
        dt_format = query_dict.get('_dtformat', None)
        if dt_format is not None:
            self.datetime_format = dt_format

        d_format = query_dict.get('_dformat', None)
        if d_format is not None:
            self.date_format = d_format

        t_format = query_dict.get('_tformat', None)
        if t_format is not None:
            self.time_format = t_format

    def format_datetime(self, datetime):
        return datetime.strftime(self.datetime_format)

    def format_date(self, date):
        return date.strftime(self.date_format)

    def format_time(self, time):
        return time.strftime(self.time_format)

    def format_decimal(self, decimal):
        return float(decimal)
