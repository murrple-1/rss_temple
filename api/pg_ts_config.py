_known_pg_ts_configs_cache: list[str] | None = []


def get_known_pg_ts_configs() -> list[str] | None:
    return _known_pg_ts_configs_cache


def load_pg_ts_configs():
    global _known_pg_ts_configs_cache

    from django.db import connection

    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cfgname
                FROM pg_ts_config
                """
            )

            _known_pg_ts_configs_cache = [row[0] for row in cursor]
    else:
        _known_pg_ts_configs_cache = None
