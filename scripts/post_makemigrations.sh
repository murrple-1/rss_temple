#!/usr/bin/env sh

INITIAL_DIR=$(dirname $(readlink -f "$0"))
MIGRATION_FILES=$(find "$INITIAL_DIR/../" -type d -name migrations -exec find {} -type f -name '*.py' \;)
echo $MIGRATION_FILES | xargs -r sudo chown $USER:$USER
echo $MIGRATION_FILES | xargs -r chmod 644
