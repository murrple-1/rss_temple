#!/bin/env sh

INITIAL_DIR=$(dirname "$0")

sqlite3 "$INITIAL_DIR/../rss_temple/db.sqlite3" 'DELETE FROM api_readfeedentryusermapping'
