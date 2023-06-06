#!/usr/bin/env sh

INITIAL_DIR=$(dirname $(readlink -f "$0"))


if [ -f "$INITIAL_DIR/.env.dev" ]; then
	. "$INITIAL_DIR/.env.dev"
fi

if [ -z "$GOOGLE_CLIENT_ID" ]; then
	GOOGLE_CLIENT_ID=''
fi

export GOOGLE_CLIENT_ID


cd "$INITIAL_DIR/../" || exit

pipenv run python manage.py runserver
