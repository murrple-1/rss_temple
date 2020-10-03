#!/usr/bin/env sh

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 [latest,<build_number>]"
    exit
fi

BUILD_NUMBER=$1

if [ -z "$CIRCLE_TOKEN" ]; then
    echo "CIRCLE_TOKEN environment variable must be set"
    exit
fi

if [ "$BUILD_NUMBER" = "latest" ]; then
    ARTIFACTS_RESPONSE=$(curl -H "Circle-Token: $CIRCLE_TOKEN" https://circleci.com/api/v1.1/project/github/murrple-1/rss_temple/latest/artifacts)
else
    ARTIFACTS_RESPONSE=$(curl -H "Circle-Token: $CIRCLE_TOKEN" "https://circleci.com/api/v1.1/project/github/murrple-1/rss_temple/$BUILD_NUMBER/artifacts")
fi

echo $ARTIFACTS_RESPONSE | grep -o 'https://[^"]*' | wget --verbose --header "Circle-Token: $CIRCLE_TOKEN" --input-file -
