_expected_ts_configs: dict[str, str] = {
    "english": "en",
    # TODO finish
    "arabic": "",
    "armenian": "",
    "basque": "",
    "catalan": "",
    "danish": "",
    "dutch": "",
    "finnish": "",
    "french": "",
    "german": "",
    "greek": "",
    "hindi": "",
    "hungarian": "",
    "indonesian": "",
    "irish": "",
    "italian": "",
    "lithuanian": "",
    "nepali": "",
    "norwegian": "",
    "portuguese": "",
    "romanian": "",
    "russian": "",
    "serbian": "",
    "spanish": "",
    "swedish": "",
    "tamil": "",
    "turkish": "",
    "yiddish": "",
}

_loaded = False

_locale_to_ts_config: dict[str, str] | None = {}


def _load_pg_ts_configs():
    global _loaded
    global _locale_to_ts_config

    if not _loaded:
        from django.db import connection

        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT cfgname
                    FROM pg_ts_config
                    """
                )

                _locale_to_ts_config = {}

                for row in cursor:
                    ts_config = row[0]
                    locale = _expected_ts_configs.get(ts_config)
                    if locale:
                        _locale_to_ts_config[locale] = ts_config
        else:
            _locale_to_ts_config = None

        _loaded = True


def locale_to_ts_config(locale: str) -> str:
    _load_pg_ts_configs()

    if _locale_to_ts_config is not None:
        return _locale_to_ts_config[locale.lower()]
    else:
        return "english"
