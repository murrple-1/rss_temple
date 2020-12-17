#!/usr/bin/env sh

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 [job number]"
    exit
fi

JOB_NUMBER=$1

if [ -z "$CIRCLE_TOKEN" ]; then
    echo "CIRCLE_TOKEN environment variable must be set"
    exit
fi

ARTIFACTS_RESPONSE=$(curl -s -H "Circle-Token: $CIRCLE_TOKEN" "https://circleci.com/api/v1.1/project/github/murrple-1/rss_temple/$JOB_NUMBER/artifacts")

TARBALL_URL=$(echo $ARTIFACTS_RESPONSE | grep -P -m 1 -o 'https://.*?build\.tar\.gz')

if [ -z "$TARBALL_URL" ]; then
    echo "No tarball URL found in response"
    exit
fi

wget -q -O "build.tar.gz" --header "Circle-Token: $CIRCLE_TOKEN" "$TARBALL_URL"

tar -xzf build.tar.gz -C /var/www/rss_temple/
rm build.tar.gz
