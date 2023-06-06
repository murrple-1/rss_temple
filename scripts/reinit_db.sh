#!/usr/bin/env sh

INITIAL_DIR=$(dirname $(readlink -f "$0"))

export GOOGLE_CLIENT_ID=''

cd "$INITIAL_DIR/../" || exit

rm db.sqlite3
pipenv run python manage.py migrate
pipenv run python manage.py loaddata api/fixtures/default.json
