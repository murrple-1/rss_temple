#!/bin/sh

export GOOGLE_CLIENT_ID=''

INITIAL_DIR=`dirname $0`

cd $INITIAL_DIR/../rss_temple/

pipenv run python manage.py runserver

