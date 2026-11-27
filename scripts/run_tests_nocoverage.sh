#!/usr/bin/env sh

INITIAL_DIR=$(dirname $(readlink -f "$0"))

if [ -z "$TEST_RUNNER_TYPE" ]; then
	TEST_RUNNER_TYPE='standard'
fi

export TEST_RUNNER_TYPE

# `pipenv run` loads `.env`, which holds the dev stack's settings (`APP_IN_DOCKER=true`,
# ...). The tests must not see them.
export PIPENV_DONT_LOAD_ENV=1

cd "$INITIAL_DIR/../" || exit

if [ "$1" = "" ]; then
	pipenv run python manage.py test --parallel auto
else
	pipenv run python manage.py test "$@"
fi
