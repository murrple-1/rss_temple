#!/usr/bin/env sh

INITIAL_DIR=$(dirname $(readlink -f "$0"))

cd "$INITIAL_DIR/../" || exit

rm api/migrations/0001_initial.py
pipenv run python manage.py makemigrations
"$INITIAL_DIR/reinit_db.sh"
