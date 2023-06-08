#!/usr/bin/env sh

INITIAL_DIR=$(dirname $(readlink -f "$0"))

if [ -z "$GOOGLE_CLIENT_ID" ]; then
	GOOGLE_CLIENT_ID=
fi

export GOOGLE_CLIENT_ID

if [ -z "$TEST_RUNNER_TYPE" ]; then
	TEST_RUNNER_TYPE='standard'
fi

export TEST_RUNNER_TYPE

if [ -f "$INITIAL_DIR/.env.test" ]; then
	. "$INITIAL_DIR/.env.test"
fi


cd "$INITIAL_DIR/../" || exit

if [ "$1" = "" ]; then
	pipenv run coverage run manage.py test --exclude-tag=slow --exclude-tag=remote api.tests
else
	pipenv run coverage run manage.py test "$@"
fi

pipenv run coverage html
