#!/bin/env sh

INITIAL_DIR=$(dirname $(readlink -f "$0"))

sqlite3 "$INITIAL_DIR/../db.sqlite3" 'DELETE FROM api_readfeedentryusermapping'
