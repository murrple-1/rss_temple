#!/bin/bash

INITIAL_DIR=$(cd `dirname $0` && pwd)

export GOOGLE_CLIENT_ID=''

cd $INITIAL_DIR/../rss_temple/

rm api/migrations/0001_initial.py
pipenv run python manage.py makemigrations
$INITIAL_DIR/reinit_db.sh
