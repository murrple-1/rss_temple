#!/bin/sh

if [[ ! -v GOOGLE_CLIENT_ID ]]; then
	GOOGLE_CLIENT_ID=''
fi

export GOOGLE_CLIENT_ID

if [[ ! -v TEST_RUNNER_TYPE ]]; then
	TEST_RUNNER_TYPE='standard'
fi

export TEST_RUNNER_TYPE

INITIAL_DIR=`dirname $0`

cd $INITIAL_DIR/../rss_temple/

if [ "$1" = "" ]; then
	pipenv run python manage.py test api.tests daemons.tests
else
	pipenv run python manage.py test "$1"
fi
