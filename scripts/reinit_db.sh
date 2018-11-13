#!/bin/bash

INITIAL_DIR=`dirname $0`

export GOOGLE_CLIENT_ID=''

cd $INITIAL_DIR/../rss_temple/

rm db.sqlite3
pipenv run python manage.py migrate
pipenv run python manage.py loaddata api/fixtures/default.json
