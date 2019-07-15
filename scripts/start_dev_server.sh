#!/usr/bin/env sh

if [ -z "$GOOGLE_CLIENT_ID" ]; then
	GOOGLE_CLIENT_ID=''
fi

export GOOGLE_CLIENT_ID

INITIAL_DIR=$(dirname "$0")

cd "$INITIAL_DIR/../rss_temple/" || exit

pipenv run python manage.py runserver
