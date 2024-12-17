#!/usr/bin/env sh

INITIAL_DIR=$(dirname $(readlink -f "$0"))

if [ -z "$TEST_RUNNER_TYPE" ]; then
	TEST_RUNNER_TYPE='standard'
fi

export TEST_RUNNER_TYPE

cd "$INITIAL_DIR/../" || exit

if [ "$1" = "" ]; then
	pipenv run python manage.py test --parallel auto
else
	pipenv run python manage.py test "$@"
fi
