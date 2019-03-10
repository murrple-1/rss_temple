#!/bin/sh

if [[ ! -v GOOGLE_CLIENT_ID ]]; then
	GOOGLE_CLIENT_ID=''
fi

export GOOGLE_CLIENT_ID

INITIAL_DIR=`dirname $0`

cd $INITIAL_DIR/../rss_temple/

pipenv run python manage.py test api.tests daemons.tests
