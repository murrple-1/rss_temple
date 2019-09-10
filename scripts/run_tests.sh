#!/usr/bin/env sh

if [ -z "$GOOGLE_CLIENT_ID" ]; then
	GOOGLE_CLIENT_ID=''
fi

export GOOGLE_CLIENT_ID

if [ -z "$TEST_RUNNER_TYPE" ]; then
	TEST_RUNNER_TYPE='standard'
fi

export TEST_RUNNER_TYPE

INITIAL_DIR=$(dirname $(readlink -f "$0"))

cd "$INITIAL_DIR/../rss_temple/" || exit

if [ "$1" = "" ]; then
	pipenv run coverage run manage.py test api.tests daemons.tests
else
	pipenv run coverage run manage.py test "$@"
fi

pipenv run coverage html
