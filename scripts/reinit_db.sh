#!/usr/bin/env sh

INITIAL_DIR=$(dirname $(readlink -f "$0"))

cd "$INITIAL_DIR/../" || exit

docker compose run --rm rss_temple python manage.py flush
docker compose run --rm rss_temple python manage.py loaddata api/fixtures/default.json
