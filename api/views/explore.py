from typing import Any, TypedDict, cast

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Feed, FeedEntry, User


class ExploreView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request: Request):
        # TODO for the time being, this will just be static data (based on my personal OPML for now), because a recommendation engine is quite an endeavour

        class FeedDesc(TypedDict):
            feed_url: str
            image_src: str | None

        class Section(TypedDict):
            tag: str
            feeds: list[FeedDesc]

        section_lookups: list[Section] = [
            {
                "tag": "Gaming",
                "feeds": [
                    {
                        "feed_url": "http://feeds.feedburner.com/GamasutraFeatureArticles",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                    {
                        "feed_url": "http://feeds.wolfire.com/WolfireGames",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                ],
            },
            {
                "tag": "Technology",
                "feeds": [
                    {
                        "feed_url": "http://rss.slashdot.org/Slashdot/slashdot",
                        "image_src": None,
                    },
                    {
                        "feed_url": "http://feeds.arstechnica.com/arstechnica/index",
                        "image_src": None,
                    },
                ],
            },
            {
                "tag": "World News",
                "feeds": [
                    {
                        "feed_url": "https://www.ctvnews.ca/rss/ctvnews-ca-top-stories-public-rss-1.822009",
                        "image_src": None,
                    },
                ],
            },
            {
                "tag": "Programming",
                "feeds": [
                    {
                        "feed_url": "http://feeds.feedburner.com/codinghorror",
                        "image_src": None,
                    },
                    {
                        "feed_url": "http://feeds.wolfire.com/WolfireGames",
                        "image_src": None,
                    },
                    {
                        "feed_url": "http://syndication.thedailywtf.com/TheDailyWtf",
                        "image_src": None,
                    },
                ],
            },
            {
                "tag": "Music",
                "feeds": [
                    {
                        "feed_url": "http://battlehelm.com/feed/",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                    {
                        "feed_url": "http://www.theblackplanet.org/feed/",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                    {
                        "feed_url": "http://www.angrymetalguy.com/feed/",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                    {
                        "feed_url": "http://www.terrorizer.com/feed/",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                    {
                        "feed_url": "http://deadrhetoric.com/feed/",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                ],
            },
        ]

        ret_obj: list[dict[str, Any]] = []
        for section_lookup in section_lookups:
            feed_objs: list[dict[str, Any]] = []
            for feed_lookup in section_lookup["feeds"]:
                feed: Feed
                try:
                    feed = Feed.annotate_subscription_data(
                        Feed.objects.all(), cast(User, request.user)
                    ).get(feed_url=feed_lookup["feed_url"])
                except Feed.DoesNotExist:
                    continue

                some_feed_entries = list(
                    FeedEntry.objects.filter(feed=feed, title__isnull=False)
                    .order_by("published_at")
                    .values_list("title", flat=True)[:5]
                )
                if len(some_feed_entries) < 1:
                    continue

                feed_objs.append(
                    {
                        "name": feed.title,
                        "feedUrl": feed.feed_url,
                        "homeUrl": feed.home_url,
                        "imageSrc": feed_lookup["image_src"],
                        "entryTitles": some_feed_entries,
                        "isSubscribed": feed.is_subscribed,
                    }
                )

            if len(feed_objs) > 0:
                ret_obj.append(
                    {
                        "tagName": section_lookup["tag"],
                        "feeds": feed_objs,
                    }
                )

        return Response(ret_obj)
